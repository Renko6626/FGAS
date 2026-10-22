# FGAS MCP 四入口实施计划

> **For agentic workers:** Use superpowers:executing-plans to implement this approved plan inline. 用户已确认接口方案；不重复索取流程批准。

**Goal:** 将 low/high 的 20/50 个工具缩减为 3/4 个，并在首层指南解释以账户、Transfer 为中心的核心模型。

**Architecture:** MCP 适配层用固定契约表连接参数化入口、按需帮助和现有应用函数。沿用现有业务服务、权限、事务和 Pydantic 校验。顶层简明模型随 overview 可读，详细业务指南按需读取。

**Tech Stack:** 现有 Python/FastAPI/Pydantic/MCP SDK 2.3.0/PostgreSQL，无新增依赖或数据库变更。

**Spec:** ../specs/2026-10-22-agent-tools-simplification-design.md（用户已确认；补充要求：顶层指南讲清核心模型与设计思路）。

## Global Constraints

- 不改前端，不运行浏览器交互；不触碰用户的 temp/ 内容。
- low 只有 help/query/propose，high 加 execute；propose 对 high 也固定待审。
- 全部50项旧能力保留；旧工具名只能返回迁移提示，不能写入。
- Patch 保留省略/null，创建保留原默认值；金额、日期、来源和事务语义不变。
- 无批量协议、代码执行、SQL、重试或新持久化；新增测试仅覆盖新契约关键行为，复用已有真实服务测试。
- 在当前工作区的新分支 feature/agent-tools-v2 实施，不新增工作树，不更改未跟踪 temp/。

## Review Focus

- 帮助中的精确参数必须能直接用于对应调用，且不得默认返回全部Schema。
- 列表/详情的identifier与filters不能静默冲突；不支持详情的对象不能接受identifier。
- high的propose保持待审，low猜execute仍被服务端拒绝，失效凭据继续拒绝。
- 修改单个字段不能清空其他字段；输入错误要指向字段，输出错误不能归咎用户参数。
- 顶层指南说明私账方向、资金/货物独立生效、结算匹配不重复记钱、盘点本身不调账，不能靠工具名字猜业务。

## Task 1: 契约表、四入口及协议测试

Files: 新建 backend/entrypoints/agent_catalog.py；修改 mcp.py、agent_schemas.py、application/agent_queries.py、agent_operations.py、tests/test_agent_access.py。

Interfaces: 固定路由选择输入/输出模型、函数及示例；新公共输入为 HelpInput/QueryInput/ProposeInput/ExecuteInput；对外 api_version=2。

- [x] 原地更新已有SDK协议测试为3/4入口，覆盖帮助、提议/直接、Patch、列表/详情、非法配对、旧名和字段错误；保留原真实业务断言。
- [x] 实现固定契约表和按需帮助；不动态 getattr 路由用户输入。
- [x] 实现四入口分派、精确输入/输出校验、迁移提示与清晰错误；保留Bearer认证和事务。
- [x] 恢复现有依赖并运行受影响检查；环境无法运行时记录原因，不伪称通过。

## Task 2: 核心模型指南与迁移说明

Files: docs/ai/guide.md；新增 docs/ai/overview.md（简短首层模型，随现有 docs/ai 进镜像）；README.md、architecture.md、旧设计/计划的替代说明；已批准设计状态。

Interfaces: MCP overview 读取 overview.md，guide 读取 guide.md，二者版本一致。overview必须不依赖读长文才能理解关键模型。

- [x] 首层用账户→Transfer→正式流水→余额/库存解释模型；用小例子说明垫付、报销、代收、收货、盘点。
- [x] 详细指南换为四入口的真实示例与按需帮助，不列旧工具；说明低/高权限及执行效果。
- [x] README/architecture说明3/4工具与v2迁移，不掩盖历史记录。

## Task 3: 集中验证与独立审阅

- [x] 一次性核对16查询、3提议、30执行的覆盖，测量新旧声明字符体积；不是永久计数测试。
- [ ] 完整数据库验收：已尝试 ./tools/run_tests.sh（仅fgas_test），连接被当前沙箱拒绝；未运行通过。其余无数据库检查已完成。
- [x] 独立只读审阅完整改动，修复具体重要问题并仅复查受影响内容。
- [x] 更新阶段记录、执行记录，提交改动；不推送或部署。

## 执行记录

- 初始状态：仅用户 temp/ 未跟踪；设计文档已有提交5108390。已建立 feature/agent-tools-v2。
- 环境：当前 .venv 缺 mcp，现有依赖安装遇沙箱代理连接拒绝；正在寻找本地已存在依赖。沙箱内无法确认宿主PostgreSQL进程；启动尝试被原有pid锁拒绝，未修改锁文件或停止服务。测试runner在连接fgas_test时被Operation not permitted拒绝，未执行重建。
- 决策：已有接口方案已获批准；计划细节自行推进。用户测试约定优先于技能的一律新增测试/逐任务重复全量验证。

- Task 1 完成实现：四入口固定分派、按需参数/结果 Schema、v2返回、旧名迁移提示、字段错误。契约测试5 passed；数据库协议用例已更新但未运行通过。
- Task 2 完成：overview.md（1,583字符）随初始化加载；完整指南、README、architecture及历史文档入口已同步。用户要求的核心模型与设计思路已在首层提供。
- Task 3 已完成无数据库验证与独立只读审阅；全量数据库验收保留未完成标记。审阅提出Patch Schema与null规则不一致、结果说明未区分嵌套结构，均已修正并复查受影响契约。
- 精简证据：low input/output Schema从10,425/52,248字符降为1,465/684；high从24,287/89,744降为2,101/912。不包含名称/描述等外壳，不能视为实际模型token节省比例。
- 49项操作帮助示例经JSON Schema及真实prepare_call解析通过，所选输出Schema合法；所有目录Patch不可清空字段的Schema与实际校验一致。保留业务默认值、明确允许的null和省略字段。
- 最终相关命令：`PYTHONPATH=$PWD/.worktrees/agent-access/.venv/lib/python3.13/site-packages .venv/bin/python -m pytest backend/tests/test_agent_access.py -k 'compact or help_describes' -q` → 5 passed, 7 deselected；compileall及diff --check通过。依赖沿用本地旧工作区的mcp2.3.0/httpx2/pytest8，不改requirements或全局配置。
- 未改前端、未运行浏览器、未更改日常业务数据、未做外部客户端v2联调、未发布部署。
