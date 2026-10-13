# 资金与货物阶段盘点实施计划

> **For agentic workers:** 确认本计划的技术方案后，使用 `superpowers:executing-plans` 在当前会话实施。只有用户明确选择委派时才使用 `superpowers:subagent-driven-development`。用户工作约定优先，不机械 TDD、不自动增加多轮审阅或浏览器交互测试。

**Goal:** 用户可以建立资金或货物盘点，以本次专属端点录入和查询普通盈亏 Transfer，结束后端点默认隐藏。

**Architecture:** 推荐分别建立资金、货物薄盘点表，端点由现有账户和位置表承载。应用层负责创建盘点及端点、修改说明、结束和只读查询；资金与数量变化继续经现有 Transfer 服务办理。没有盘点明细、通用关联表或第二套账本。

**Tech Stack:** 沿用 FastAPI / Pydantic、SQLAlchemy 2 / PostgreSQL、Vue 3 / TypeScript / Vite / Naive UI，不新增依赖。

**Spec:** [architecture.md 第 9 节](../../../architecture.md)、[Transfer 操作模型](../../transfer-model.md)、[README 最顶层产品原则](../../../README.md)。

**状态：** 2026-10-14 用户确认按本计划实施，选择 subagent-driven，`gpt-6.1-sol low` 执行、`gpt-6.1-sol medium` 审阅。物理表、接口和权限方案已获授权；只实施计划内功能，不增加高并发或边角机制。

## 1. 全局约束

- Transfer 是第一公民。盘点入口只组织记录和预填端点，用户仍能看清来源、去向、金额或数量及生效时点。
- 单社团、人民币；金额为整数分，数量为整数，不做估值。
- 盘点状态仅为 `in_progress` / `ended`。结束只默认隐藏端点，不停用、不冻结业务、不自动完成或取消转移。
- 不增加结构化实点明细、差异结清状态、历史错账匹配、请求回放、自动重试、额外审批队列或自动去重。
- 复用现有 HTTP 事务和简单串行锁。创建盘点与两个端点一次提交；不增加保存点或请求恢复机制。
- 不清空日常数据库、不迁移旧账、不启动服务、不发布或推送。新增表沿用现有 metadata 建表方式。
- UI 文案自然具体，不使用“xxx · xxx”拼接。默认只构建和必要截图，不自动点击或填表。
- 新增永久测试只覆盖本次关键行为，复用已有数据库夹具及资金/库存测试文件；相关检查集中执行。

## 2. 已确认技术方案与取舍

### 数据与模块

推荐两个表：

| 模型 / 表 | 字段 |
| --- | --- |
| `FundStocktake` / `fund_stocktakes` | `id`、`name`、`description`、`status`、`gain_account_id`、`loss_account_id`、`created_by`、`created_at` |
| `StockStocktake` / `stock_stocktakes` | `id`、`name`、`description`、`status`、`gain_location_id`、`loss_location_id`、`created_by`、`created_at` |

两表使用已有 UUID、UTC 时间及用户外键；名称非空、最长 200 字符，说明默认空文字。状态有数据库检查约束。两个端点外键均非空、分别唯一，且不能相同。服务自动创建端点，客户端不能指定或重新绑定已有端点；不保存 Transfer ID。

资金端点命名为“{盘点名称}（资金盘盈）”“{盘点名称}（资金盘亏）”，分别为非资金收入／费用账户。货物端点命名为“{盘点名称}（货物盘盈）”“{盘点名称}（货物盘亏）”，分别为 active 的外部 `adjustment_gain` / `adjustment_loss` 位置。不同盘点允许同名，编号区分，端点不复用。

首版名称和端点关联创建后固定，允许修改说明及标记结束；无删除、重开或重新绑定接口。普通目录入口不允许改变专属货物端点的边界性质，以免破坏盘点方向；不新增另一套启停状态。

新增 `backend/application/stocktakes.py` 组织两类盘点，新增 `backend/infrastructure/stocktake_store.py` 实现小型持久化与端点归属查询。盘点服务调用现有账户／位置创建逻辑，不直接修改资金或库存流水。一个应用文件承载两类薄记录，避免按每个动作继续拆模块。

取舍：分表可以用明确外键引用现有账户或位置，避免一张表中的四组可空端点字段及组合约束；少量同形字段重复可接受。统一一个应用入口和一个盘点页面，操作体验保持一致。单表多态方案暂不采用。

### 权限与接口

推荐已登录且 active 的用户均可读取；受信任用户和管理员可以创建、修改说明和结束盘点。这沿用目录管理权限，不新增盘点申请／审批流程。不受信任用户仍可使用已创建端点提交普通 Transfer，由原业务规则审批。

两组 API 均采用 `/api/fund-stocktakes` 和 `/api/stock-stocktakes`：

| 方法 | 路径 | 输入 / 输出 |
| --- | --- | --- |
| GET | 集合路径，支持 `status` 可选筛选 | 返回盘点列表，含上述字段及端点名称；默认包含所有状态 |
| POST | 集合路径 | `{name,description?}`；创建盘点及两个端点，返回盘点，201 |
| GET | `/{id}` | 返回 `{stocktake,transfers}`；复用现有资金／货物 Transfer 返回结构 |
| PATCH | `/{id}` | `{description}`；仅修改说明，返回盘点 |
| POST | `/{id}/end` | 无业务参数；设为 ended，返回盘点；已结束时直接返回当前记录 |

无新增“盘点调整提交”API。所有调整继续调用原资金预览／提交或 `/api/stock-transfers`，不要求盘点 ID。

资金详情查询 `source_account_id = gain_account_id OR destination_account_id = loss_account_id`，并展示这些记录的既有冲销记录，即使冲销方向反过来也能查到；用现有 `reversal_of`，不增加关联表。不显示“差异已结清”或额外净额汇总。

货物详情查询 `source_location_id = gain_location_id OR destination_location_id = loss_location_id`。不按日期截断，不排除结束后新增记录。两类详情均保留待批、拒绝、取消和有效记录的普通状态。

应用函数：`list_stocktakes(db, kind, status=None)`、`create_stocktake(db,user,kind,data)`、`get_stocktake(db,kind,id)`、`update_description(db,user,kind,id,description)`、`end_stocktake(db,user,kind,id)`；`kind` 为 `fund|stock`，HTTP 路由提供固定 kind。

### 默认隐藏与编辑器

账户及位置目录 API 继续返回全部对象，附加可空 `stocktake:{id,name,status}` 元数据，所属端点通过盘点表查询得到；普通对象为 null。旧记录名称、详情、余额查询始终能解析历史端点。

选择器默认排除 ended 的盘点端点，提供“显示已结束盘点端点”开关。已有选中项仍可见，不因筛选清除选择。账户／位置本身不因盘点结束而停用，后端普通 Transfer 不因 ended 拒绝提交。

在现有 `EndpointSelector.vue` 和新增的小型 `LocationSelector.vue` 中分别落实账户／位置选择与隐藏；资金和货物所有端点录入入口使用相应选择器，避免只改盘点页。位置选择器仅收敛这次确实需要的选择与筛选，不增加请求或状态恢复机制。

资金编辑器增加可选 `initial` 输入用于预填；货物编辑器增加可选 `initial` 和轻量 `open(initial?)` 暴露方法。盘点页面“新建盘盈／盘亏转移”仅调用原编辑器：资金预填专属端点，另一端默认首个组织资金账户且可修改；货物预填专属端点和 action_kind，另一端由用户选择实际位置。保持普通编辑器可修改语义，查询归属以最终端点为准。

## 3. 实施任务

### Task 1：薄盘点模型、应用服务和 API

**Files:** 修改 `backend/infrastructure/models.py`、`backend/entrypoints/schemas.py`、`backend/entrypoints/http.py`；新增 `backend/infrastructure/stocktake_store.py`、`backend/application/stocktakes.py`；修改已有 `backend/tests/test_funds.py`、`backend/tests/test_stock_transfers.py`。

- [x] 增加两张薄表和输入 schema，按第 2 节实现读取、创建、修改说明和结束 API。写操作在现有锁内刷新用户和角色，所有创建共用 HTTP 事务。
- [x] 创建专属端点并建立关联，盘点创建不生成资金分录或库存流水。实现方向查询和资金冲销历史展示，复用原 Transfer view；多记录详情使用现有一致读取快照。
- [x] 新增一个资金行为场景：普通用户创建被拒绝；可信用户创建后金额仍为零；普通 Transfer 经本次盘盈收入端点入资金池 100 元、盘亏支出 20 元后资金 80 元，两笔均可从盘点详情查到；冲销 20 元盘亏后资金恢复 100 元，盘点可查到原记录及冲销；结束不改变金额，说明可更新。
- [x] 新增一个库存行为场景：创建盘点不改数量；从本次盘盈端点向实际位置录入 10 本，批准后仍为 0，手动完成后为 10；盘亏 2 本完成后为 8，本次两条 Transfer 可查；结束后仍能通过同一端点建立并完成普通盘盈 1 本，最终为 9，盘点能查到。
- [x] 在资金测试文件增加简短失败回滚场景：复用现有失败注入做法，第二端点保存时报错，盘点和第一端点均无残留。不为两类复制整套故障测试。

**验收证据：** 两类 HTTP 记录、正式余额/数量、状态和冲销历史正确；使用专用 fgas_test，集中验证见 Task 3。

### Task 2：盘点页面、普通编辑器预填与端点隐藏

**Files:** 修改 `backend/application/catalogs.py`、`backend/application/warehouse_catalogs.py` 以附加归属元数据；修改 `frontend/src/api/funds.ts`、新增 `frontend/src/api/stocktakes.ts`、`frontend/src/views/StocktakesView.vue`、`frontend/src/components/LocationSelector.vue`；修改 `frontend/src/App.vue`、`frontend/src/components/EndpointSelector.vue`、`frontend/src/components/TransferEditor.vue`、`frontend/src/components/StockTransferEditor.vue`、`frontend/src/components/StockAdjustmentEditor.vue`。已有垫付和偿还编辑器按选择器引用情况做必要局部调整，不重写业务逻辑。

- [x] API 类型与第 2 节字段一致；在目录响应加入端点所属盘点，普通账户/位置保持原字段语义。加入专属货物端点边界性质不可变的局部校验。
- [x] 现有主导航新增“盘点”，页面用资金／货物分类呈现列表、说明和状态。所有身份可读，可信身份可创建、编辑说明和结束；结束按钮不要求所有 Transfer 已完成。
- [x] 盘点详情复用 `TransfersView` / `StockTransfersView` 展示普通状态和详情，资金冲销照常展示；新建按钮打开原编辑器并预填。不增加独立调整单或隐藏来源去向的提交表单。
- [x] 实现所有相关选择器中的默认隐藏和显示开关：普通资金转移、垫付去向、钱货组合、普通货物转移、原单盈亏调整。偿还资金来源仍只允许组织资金账户。
- [x] 从盘点入口提交后刷新记录和目录；结束后刷新归属状态，保留历史名称和已有选择。沿用 busy、错误提示和人工查询，无自动重试。
- [x] 在 Task 1 已有两类场景中补端点元数据检查：进行中/结束状态正确，普通对象无盘点归属；目录仍返回结束端点。对专属货物边界性质修改的拒绝，在库存场景补一个行为断言。

**验收证据：** 类型检查与构建；按需截图检查页面和窄屏展示，不自动操作浏览器，不新增页面样式测试。

### Task 3：集中验证与文档交付

**Files:** 本计划、`architecture.md`、`docs/transfer-model.md`、`docs/prototype-status.md`、`README.md`。

- [x] 运行 `./tools/run_tests.sh`，要求打印 `Test database: fgas_test` 且全部通过。已有 runner 仍覆盖三个测试文件，无新测试框架或云端 CI。
- [x] 运行根目录 `npm run build`，要求 vue-tsc 与 Vite 成功。运行 `git diff --check`。
- [x] 对照第 1 节范围检查实际代码：无盘点明细/差异状态机，无额外请求恢复，盘点结束仅改变默认展示，所有正式变化来自原 Transfer。
- [x] 文档记录实际表、API、权限、端点隐藏和资金冲销查询；更新已实现/待实现状态，报告实际命令结果和未进行的浏览器、开发库及部署验收。
- [x] 检查通过后停止追加验证；不自动提交、合并、推送、重置日常数据库或部署。

## 4. 核对重点与计划自检

- 创建盘点只创建资料，资金/数量正式变化只能来自原 Transfer（Task 1 两类主场景）。
- 结束是默认隐藏，普通业务仍可办理；目录保留历史对象，已有选择不能被筛选清空（Task 1、2）。
- 资金冲销反转端点方向也能在本次盘点中追溯（Task 1 资金场景）。
- 原单关联盈亏和本次盘点端点归属同时成立，不互相代替；无原单的阶段盘点调整也合法（沿用 warehouse.validate，Task 1、2 源码检查）。
- 用户仍能看清实际端点和生效时点；盘点结束不宣称调整全部生效或差异全部结清（Task 2 页面与文案检查）。

自检：已覆盖两类薄记录、专属端点、双入口、查询、状态、默认隐藏、文字说明及原 Transfer 流程。权限、两表、API 和模块方案已获确认，没有增加计划外机制。


## 5. 2026-10-14 实施与集中检查记录

Task 1、2 已实现并通过逐任务规格与质量审阅；Task 3 完成文档及既定集中检查。专用 `fgas_test` 测试 25 passed in 11.65s；根目录构建 vue-tsc / Vite 通过，2,696 modules，5.52s；`git diff --check` 通过，三项退出均为 0。原始输出见 `.superpowers/sdd/2026-10-14-stocktakes-plan/task-3-checks.log`。范围核对按实际薄盘点服务和持久化及已完成任务审阅，不新增广泛审查或机制。

实现仍在隔离分支，未合并、推送、部署或初始化日常库。未截图或执行浏览器交互验收；列表和编辑器运行体验尚未浏览器验证。检查通过后停止追加验证，最终分支审阅由主任务安排。
