# Agent 接入下一步实施计划

状态（2026-10-27）：Task 1–4 已实现并分别审阅通过；集成后端检查 84 passed，前端同码构建通过。Task 5 定向复测与证据整理已完成：13个最新选定场景11通过、2回答部分符合；保留早轮反例，未全26场景复测或生产验收。版本及最终证据见 [后续证据](../../ai/2026-10-27-agent-access-followup.md)。下方待办框保留原实施清单，不表示功能仍未开发。编号按用户后续确认直接同步 `0001`，不新增 revision、不迁移或回填旧库，日常 `fgas` 未改。

> 使用 subagent-driven-development 顺序派发独立实现与审阅。

**Goal:** 落实接入实测总结的身份、业务编号、交接、库存计划口径，并定向复测。

**Architecture:** 沿用模块化单体、现有四个 MCP 工具及 hash 导航；公开业务契约使用 code，UUID 只保留内部关联。

**Tech Stack:** 现有 Python/FastAPI/SQLAlchemy/PostgreSQL 与 Vue/TypeScript/Naive UI，无新增依赖。

**Spec:** `docs/superpowers/plans/2026-10-27-agent-access-next-steps.md`。用户已确认推荐方案，随后明确编号模型直接同步现有 0001 基线，不新增 Alembic revision、不做旧数据迁移/回填。

## Global Constraints

- 正式流水及历史不可改写；账户、授权、冲销、匹配与整笔完成业务规则不变。
- 人工 HTTP 只用 Cookie，MCP 只用 Bearer，所有业务通过应用服务及原授权。
- 不增加框架、服务、缓存、队列、状态机、自动重试、请求恢复、幂等键、部分完成、利润或盘点能力。
- 目录自动不可编辑编号：FA/SA/M 四位；资金单 FT、货物单 ST、完成申请 SC 六位；前缀后连字符，数据库序列生成，唯一稳定允许缺号，超出位数不得截断。
- 公开业务输入/输出一次切换 code，不保留 UUID 参数兼容；认证技术标识不在编号改造范围。
- 不删除现有 Alembic 初始化机制；仅更新 0001 基线，不新建 revision，不回填旧库。
- 测试仅连接 fgas_test，重建前备份；不改日常 fgas，不读取或输出密钥。定向模型只用独立 fgas_benchmark，恢复前备份。
- 默认运行相关已有检查；新增测试仅填补关键行为/具体故障覆盖，优先扩展既有 HTTP/MCP 用例。不做浏览器点击/填表、无新 CI。
- 主 agent 协调独立审阅；实现和审阅 agent 均不得再派子 agent。工作目录 /data/sunyunbo/www/FGAS/.worktrees/agent-access-next-steps。多人共用文件，不覆盖他人改动。

## Review Focus

- 管理员 low 的身份查询不能把用户角色当作连接执行权限。
- code 解析在应用服务，原授权不被协议适配或查找绕过。
- 完成申请 SC 与父单 ST、付款 FT 与原收支 FT 的引用保持清晰。
- 内部调拨计划明细只计一次，账户筛选不改变组织边界定义。
- 历史计划不可用为 null；分页重复返回全筛选范围汇总，不逐页相加。

### Task 1: 当前身份与业务边界说明

**Ownership:** `backend/application/agent_queries.py`、`backend/entrypoints/agent_schemas.py`、`agent_catalog.py`、`mcp.py`、`backend/tests/test_agent_access.py`、`docs/ai/overview.md`、`guide.md`、`frontend/public/agent-setup.md`。

- [ ] 在现有 query 注册单对象 `me`，只返回 `api_version/data`，data 为 `{user:{display_name,role},connection:{name,level}}`，数据来自当前 AgentAccess。不接受 identifier 或非空 filters，不新增身份资料/存储，help 对 me 不展示列表/分页契约。
- [ ] 接入验证顺序为核心说明、help、me、正常业务只读查询、报告真实身份及等级。保持现有客户端配置及重载说明。
- [ ] 权限交接并列人工网页和合法已授权 high Agent，使用目前页级入口；保留原单/原付款/原申请，说明已办部分，不自动换 key 或提权。
- [ ] 混合利润任务先办可支持登记，再说明尾款/未结列表不是全量收入费用，无法确定利润，high 不补成本。未整笔到货先核实事实，不能误整单完成。
- [ ] 复用原生 MCP 测试验证普通 low/admin low/admin high、拒绝不支持参数、认证及低权限限制；更新指南版本。只运行相关检查并记录命令输出。
- [ ] 自审并提交；完整报告写入工作区 task-1-report.md。

### Task 2: 后端业务编号统一

**Ownership:** 后端 `application/`、`infrastructure/`、`entrypoints/`、`migrations/versions/0001_baseline_schema.py`、`backend/tests/` 中受影响文件；必要帮助说明同步。暂不改 frontend、基准脚本。

**Interfaces:** 各业务实体输出 `code`；关系 `*_id` 公开改为 `*_code`，复数 `*_ids` 改 `*_codes`；保留内部 ORM 主外键与内核 UUID。MCP 详情及动作 identifier 一律业务 code；settlement_overview 用 identifier 指定 FA 私账，不再 filters.account_id。SKU 仍人工维护现有 code。

- [ ] 为 FundAccount/StockAccount/Member/Transfer/StockTransfer/StockTransferConfirmation（以实际类名为准）增加非空唯一 code，以数据库原生序列和 server default 生成；保证种子与 ORM 插入均生成，目录号不可编辑。同步现有 0001 基线，不新增 revision 或旧库回填。
- [ ] 在既有应用服务解析业务 code；保留内部 ID 用于编排和持久化。所有公开业务 DTO、关系、筛选、动作和结果一致切换，去掉不需要对外的 UUID（认证/操作者技术标识除外）。内部审计/分录/明细无须新编号；通过父单和 SKU 表达关联。
- [ ] HTTP 路径保留现有资源名称但定位值改 code；MCP schema/帮助示例一致。资金 q 搜索补齐，货物 source_reference 精确筛选、q 覆盖原始引用；多候选仍列表，不猜选。
- [ ] 已暂停盘点保持暂停，保留代码可适配内部调用，不新增盘点编号或入口。
- [ ] 必要适配原有真实 HTTP/MCP、业务约束与基线检查。补最少核心编号行为断言，避免为字段删除新增测试。重建测试库前必须备份，明确 DATABASE_URL 为 fgas_test；不访问其他业务库。
- [ ] 集中运行后端已有检查（仅 fgas_test），记录结果；自审提交，完整报告 task-2-report.md，列出 task3 消费的最终公开字段。

### Task 3: 前端、定位链接与基准入口适配

**Ownership:** `frontend/src/`、`scripts/benchmark.py`、`benchmarks/gensokyo-circle-v1/`、`frontend/public/agent-setup.md` 及相关 docs/ai 示例；不改后端业务代码，遇接口问题报告主 agent。

**Interfaces:** 消费 Task2 的真实 code 契约，业务对象以 code 为定位键，用户身份/Agent 密钥等技术 ID 维持现有含义。

- [ ] 同步资金/货物账户、联系人、资金单、货物单、完成申请、结算 API 类型、表单、选择器、详情及复制按钮；名称为主、业务号辅助。SC 申请号与 ST 父单号清楚区分，公开业务流程不依赖 UUID。
- [ ] 复用现有 App.vue hash：`/#transfers?code=FT-000123`、`/#stock?code=ST-000123`、`/#settlements?account_code=FA-0001`。解析后加载并展示对象，不执行动作，保留同页登录 hash；真实 SSO 后允许重新开链接，不新增认证返回恢复机制或路由框架。
- [ ] 更新接入/业务帮助的实际 code 示例及可用定位链接，仍并列人工/high，不强迫选路。
- [ ] 基准加载/核对仅经真实 HTTP 公开 code，不查 SQL 取 UUID；mapping.json 映射符号到 code。保持固定情景事实/日期/黄金金额数量，调整双路线验收与身份要求，模型看不到黄金答案。此任务不重置基准库或跑模型。
- [ ] 运行 npm run build、Python 编译等相关静态检查；无浏览器交互，无新增永久样式测试。自审提交并写 task-3-report.md。

### Task 4: 在途方向和计划汇总

**Ownership:** `backend/infrastructure/inventory_queries.py`、`backend/application/stock_queries.py`、相关 HTTP/MCP schema/query/help、已有库存测试、`frontend/src/api/warehouse.ts`、`InventoryView.vue`、`scripts/benchmark.py` 中库存核对以及业务说明。

- [ ] 账户库存行用 `incoming_planned_quantity` / `outgoing_planned_quantity` 替换混合 `in_transit_planned_quantity`。仅已批准尚未完成的单据，分别按去向/来源计量，正式 quantity 仍来自 StockMove。
- [ ] `totals` 逐 SKU 返回 `sku_code,sku_name,unit,quantity,incoming_to_org_quantity,outgoing_from_org_quantity,internal_transfer_quantity`，三种计划 external→internal / internal→external / internal→internal 各明细计一次。保留已有必要估值说明，但不新增利润/估值功能。
- [ ] 账户/负责人过滤先限定相关账户，再以任一端涉及范围选计划明细且只计一次；分类仍按 internal/external，不能把离开选中仓库当组织出库。SKU 筛选同样作用于计划汇总。默认全部组织，过滤时当前筛选范围；每页 totals 重复同一范围，不可相加。
- [ ] 历史 as_of 的两项行计划和三项汇总计划均为 null；不建历史快照、不推算过去在途。当前 0 与历史 null 区别明确，不新增 HTTP 历史页面。
- [ ] 前端显示正式数量、待完成流入/流出和逐 SKU 三类汇总，清楚标注筛选范围及“已批准但尚未确认完成”，不称物理实时运输/预占/可售。
- [ ] 扩展原库存/HTTP/MCP场景覆盖内部调拨不重复、筛选、分页及历史 null。基准 BAD-01-A 正式297，外部入库计划120，内部调拨10、对外0，计划明细130。运行相关已有检查及 build，自审提交写 task-4-report.md。

### Task 5: 定向复测与最终现状记录

**Ownership:** 主 agent 负责真实模型运行和备份；实现 agent 仅负责基准验收规则补齐、必要命令支持、真实证据整理到 docs/ai 与 prototype-status/README/architecture/AGENTS 相应现状，不调整无关历史。

- [ ] 先阅读私有原始实测报告及已有运行器，保留 Luna high/Codex 原生 MCP 接入路径和固定事实；不将模型换成其他模型后声称同口径复测。
- [ ] 主 agent 仅在 fgas_benchmark 备份后重置/加载，定向 C01、L02、F02—F05、X01/X02 两档、H02及编号相关审批/匹配主链；每个独立写任务恢复基线，补问续接保持当前基线。
- [ ] 分别记录账本变化、回答语义、参数失败、工具数、耗时和人工步骤。模型不得获取源码/答案/数据库/Cookie；凭据不写仓库，不在报告泄露。
- [ ] 若实际模型受当前可用性限制，准确记录已尝试命令和限制，不伪造验收或用软件测试替代；继续完成可执行检查。
- [ ] 最终完整改动在 fgas_test 集中运行 ./tools/run_tests.sh 以及 npm run build；前面同码已跑过全量且无新后端改动时可复用真实证据。记录实际结果及未验收项，形成对比总结。
- [ ] 自审提交，task-5-report.md；主 agent 派发最终全分支审阅，仅根据具体核心问题修正，不扩展边角机制。
