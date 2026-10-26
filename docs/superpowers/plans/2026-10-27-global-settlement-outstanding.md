# 全局待结算匹配 Implementation Plan

> Use superpowers:executing-plans；主 agent 顺序执行，保留已有改动。

**Goal:** 全局查询已过账且剩余未匹配金额大于0的原收支和结算付款；low/high可读，MCP写匹配仍仅high。

**Architecture:** HTTP与MCP共享settlements.outstanding，复用现有有效匹配、私账分类和只读快照；不增加存储或顶层工具。

**Tech Stack:** 现有Python/FastAPI/SQLAlchemy/PostgreSQL/MCP SDK。

**Spec:** docs/superpowers/specs/2026-10-27-global-settlement-outstanding-design.md，用户已确认实施。

## Constraints / review focus

- 仅fgas_test运行数据库测试；先暂停试用后端，不触碰日常库。
- 保留原私账overview和high匹配动作；无新依赖、表、字段、前端交互或CI。
- 两侧未匹配不可相加为待付款；零余额私账仍可能有待匹配记录。
- 覆盖部分匹配、多私账、费用/代收、冲销恢复、全历史、过滤和分页；低权限原生MCP只能查。

## Task 1: 全局应用服务和HTTP

Files: backend/application/settlements.py、backend/entrypoints/http.py、backend/tests/test_settlements.py。

- [x] 现有测试文件补真实HTTP行为：零净余额仍未匹配、部分匹配与冲销、方向/类型/账户筛选、分页及不改变账本。
- [x] 在显式fgas_test上运行目标测试，确认因接口缺失失败。
- [x] 实现 `outstanding(db, account_id=None, direction=None, kind=None, page=1, limit=20)`；一次快照按现有匹配计算读取，稳定排序后分页。人工HTTP使用Cookie身份、Literal与页码边界校验。
- [x] 运行目标测试及既有结算测试。

## Task 2: MCP契约和权限

Files: backend/application/agent_queries.py、backend/entrypoints/agent_schemas.py、backend/entrypoints/agent_catalog.py、backend/tests/test_agent_access.py。

- [x] 给现有原生MCP集成测试补low查询、输出Schema和匹配拒绝行为；复用现有high匹配测试验证更新后消失。
- [x] 注册settlement_outstanding输入/输出和help；金额复用_result，分页复用_database_page。输出保留total/limit，额外提供has_more/filters。
- [x] 运行相关原生MCP与契约检查；不增加顶层工具和写权限。

## Task 3: 文档、集中验证与交付

Files: docs/ai/overview.md、docs/ai/guide.md、backend/entrypoints/mcp.py、README.md、architecture.md、docs/prototype-status.md。

- [x] 同步查询示例、两侧金额口径、low/high边界与指南版本。
- [x] 显式指定fgas_test运行 ./tools/run_tests.sh；git diff --check。无本轮前端修改，不重复构建。
- [x] 审阅实际差异，核对无越权、旧匹配规则改变或额外机制；阶段记录报告实际结果。
- [x] 检查主目录文件未被他人修改后同步本轮修改；重启本地后端并确认健康和新接口可用。不提交、合并或发布。

本机目标测试命令沿用项目.venv和fgas_test连接，连接串不写入文档。测试命令均显式FGAS_TEST_DATABASE=1及AUTH_MODE=development，完整脚本自身还会核对真实库名。


## 实际结果

用户已确认方案，全部任务已执行。结算7passed、目标原生MCP2passed、完整后端73passed（30.48s，fgas_test）；差异检查通过，独立只读审阅无重要问题。新resource保持3/4个顶层工具和high匹配权限。未进行真实模型试用、公网联调或生产发布。

已校验主目录无并发修改后同步本轮文件，本地后端重启成功；经5188前端代理的HTTP和原生MCP low查询均成功，临时连接已停用。未提交或发布。
