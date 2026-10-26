# 货物账户统一负责人 Implementation Plan

> 使用executing-plans，由主agent顺序实施，保留既有结算查询及文档改动。

**Goal:** 货物账户只维护一名可选负责人，允许变更/清空，自动记录历史；MCP low可读、high可改。

**Architecture:** 复用StockAccountCustody为唯一负责人来源，移除StockAccount.member_id存储列；现有账户create/update的member_id写入负责人历史，列表/库存的member_id投影当前负责人。详情按需读取历史，不新增顶层工具或历史表。

**Spec:** docs/superpowers/specs/2026-10-27-stock-responsible-design.md。用户补充确认：开发阶段直接重建库，不处理旧数据迁移；同步0001建库基线，不加兼容、回填或未知历史。

## 约束

- 仅重建fgas_test，先备份并暂停试用后端；不改日常fgas库。恢复服务前核对主目录与已测试文件一致。
- 保留资金账户联系人、库存正式流水、公私分类、既有角色与Agent权限。
- 只减少一个人员概念，去掉custodian_id/current_custody/set_custody的重复公开接口；不增状态机、队列、自动恢复或迁移机制。
- 前端沿用当前Naive UI样式；只类型检查/构建及必要截图，不浏览器自动点击/填表。

## Task 1: 单一来源和读取历史

Files: models.py、0001_baseline_schema.py、store.py、stock_store.py、directory_views.py、catalogs.py、warehouse_catalogs.py、inventory_queries.py、stock_queries.py、http.py、test_stock_transfers.py。

- [x] 新增一个真实HTTP用例覆盖首次负责人、更改/清空、不变不新增历史、外部账户、筛选、库存不变和低权限修改拒绝；先运行看缺失详情或历史而失败。
- [x] 删除StockAccount.member_id列及基线外键；资金账户列保留。历史表原约束保持。
- [x] 新增历史读取和单一负责人投影；账户创建、编辑经同一应用服务维护历史，不保存第二个当前人字段。详情GET /api/stock-accounts/{id}返回responsibility_history（姓名、起止时间、设置/结束操作者），普通列表不带历史。
- [x] 统一member_id库存/目录筛选；移除旧custody写路由和custodian_id参数。修改已有相应测试以保持原有库存和筛选断言。

## Task 2: MCP与页面

Files: agent_queries.py、agent_schemas.py、agent_catalog.py、agent_operations.py、frontend/src/api/accounts.ts、CatalogView.vue、InventoryView.vue。

- [x] 现有stock_accounts query增加identifier详情；输入/输出Schema与帮助一致，low可查历史。stock_account/create/update的member_id设置负责人，high保护不变；移除set_custody动作和重复返回字段。
- [x] 页面列表和编辑只显示一个负责人；复用现有弹窗改为只读历史表，显示起止时间和操作人。库存筛选使用member_id与同一负责人。
- [x] 复用已有Agent查询及原生MCP用例核对负责人/历史读取和high修改，保留全部原有权限与库存断言。

## Task 3: 验证、文档和交付

Files: docs/ai/overview.md、guide.md、mcp.py、README.md、architecture.md、transfer-model.md、prototype-status.md。

- [x] 同步单一负责人、历史、member_id筛选和接口变更；更新指南版本及开发基线重建说明，不描述旧数据迁移。
- [x] 显式fgas_test运行 ./tools/run_tests.sh，包含基线/模型一致性及原业务回归；npm run build；git diff --check。
- [x] 一次范围有限的只读审阅，修具体核心问题，不展开理论防御或大范围复审。
- [x] 核对主目录没有并发修改后同步成果，启动本地10622后端并验证5188页面/接口；记录实际验证和未做项。不提交、合并或发布。

首次记账身份配置仍是独立待实施方案，本次不扩展User关联字段。

实际集中验证：74 passed（31.03s，fgas_test）、npm run build通过（6.14s）、独立只读审阅无重要问题。备份路径及本轮范围见prototype-status。

已核对主目录无并发修改后同步成果，恢复10622及5188代理访问；真实HTTP与原生MCP low历史查询成功。未提交或发布。
