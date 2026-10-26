# 东方社团Agent基准实施计划

> **For agentic workers:** 按确认设计分工执行，项目AGENTS.md的范围与集中验证要求优先。

**Goal:** 以可读SKU代号提供商品入口，并加载可重复的东方社团基准和24张任务卡。

**Architecture:** 保持现有分层；应用服务解析SKU代号为内部关联；同步0001，不做迁移、回填或兼容。基准脚本通过受控本地API的真实HTTP业务入口加载。

**Tech Stack:** 现有Python/FastAPI/SQLAlchemy/PostgreSQL、Vue/TypeScript/Naive UI。

**Spec:** `docs/superpowers/specs/2026-10-27-agent-benchmark-design.md`

## Global Constraints

- 不改日常fgas库；pytest只在fgas_test，重建前备份；业务基准fgas_benchmark。
- 不新增依赖/CI/测试框架；不自动点击填表；不扩订单、利润、盘点或请求恢复。
- 商品完整name，无specification；code唯一、必填、转大写、去重；tags表达类别和角色。

## Review Focus

- 创建/修改均拒绝规范化后的重号，单据明细不重复SKU。
- 商品输入和筛选使用sku_code，授权与待审逻辑不变。
- 多角色同人本标签完整，旧款停用不隐藏角色其他商品。
- reset先备份，仅处理基准库；不写流水表、不向未知服务灌入数据。
- 独立预期库存297及结算样本，不将实际读回当黄金答案。

### Task 1: 后端和已有测试（主agent）

Files: backend目录/库存/Agent服务、schemas/catalog、models、0001、backend/tests。

Interface: SKU `{id,code,name,unit,tags,active,avatar_url?}`；目录filters code/q/tag/active；SKU编辑identifier=code。货物输入lines仅`{sku_code,quantity}`，库存/货物转移/数量流水filters sku_code。输出保留内部sku_id并新增sku_code，完整name。

- [x] 核心HTTP用例先覆盖唯一代号、按代号录单与查询，观察未实现失败。
- [x] 实现新契约、更新0001，复用原授权和记账路径。
- [x] 适配已有测试，不删除有效断言，不为字段删除增用例。

### Task 2: 前端（独立所有权）

Files: frontend/src，特别api/warehouse.ts、SKU目录、库存、货物编辑及展示。

Consumes: Task1 HTTP契约。Produces: 代号/完整名称/标签编辑、搜索筛选，商品录单和查询用sku_code；不展示UUID兜底。

- [x] 使用现有Naive UI，不重设计，不新增永久测试。
- [x] 完整改动集中`npm run build`。

### Task 3: 基准包和脚本（独立所有权）

Files: scripts/benchmark.py、benchmarks/gensokyo-circle-v1/；不修改业务后端或前端。

Consumes: Task1契约及现有人工API。Produces: init/reset/serve/check、固定32SKU、24任务卡、黄金答案、本机私有凭据。

- [x] 写固定业务事实与任务；只有一个公账、固定收银苏禾、分散储藏室/宿舍。
- [x] 环境准备后通过真实HTTP完成目录、资金、审批、货物完成、结算与签发，失败停止。
- [x] check读回32、类别16/8/8、启停28/4、库存297和位置、在途120/10、结算及负责人。

### Task 4: 集成和验证（主agent）

- [x] 备份fgas_test，集中`./tools/run_tests.sh`及`npm run build`。
- [x] 基准init/check，保留已加载数据库，记录真实结果；不运行模型任务。
- [x] 同步README/架构/AI指南/原型状态的新SKU入口。
- [x] 最终一次审阅，仅处理具体错误，不扩理论边角机制。

## 执行记录

实施时使用工作目录`.worktrees/agent-benchmark`、分支`codex/agent-benchmark`，完成后按用户要求归并至main；原目录已有.gitignore修改不变。后端、前端、数据包按明确文件所有权并行；主agent负责集成与集中验证。

集中结果：后端74 passed（30.28s）、前端vue-tsc/Vite通过；基准reset和独立check通过，非空init按预期拒绝；一次最终只读审阅的F01账户名问题已修正。数据已保留，模型任务未运行。
