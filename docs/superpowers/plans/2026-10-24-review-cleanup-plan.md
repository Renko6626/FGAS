# 审阅问题核实与修复计划

**目标：** 修复已确认的页面状态与 MCP 生命周期问题，整理局部重复和文档偏差；不扩展业务功能。

**路线：** 沿用 FastAPI / SQLAlchemy / PostgreSQL、Vue / TypeScript / Naive UI。无新增依赖、数据库字段、迁移、请求队列或恢复机制。用户已授权由若干子代理并行修复；前端、后端应用与基础设施、MCP 分别实施，主代理负责文档、整合与集中验证。

**依据：** 用户本轮审阅清单、AGENTS.md、architecture.md、deploy/README.md，以及 2026-10-24 工作区静态核查。

## 核实结果

| 条目 | 结论与限定 |
| --- | --- |
| 部署路线 | 成立。architecture.md 只提 Compose 与 PM2，但 deploy/README.native.md 和服务文件提供 systemd。deploy/README.md 已有原生部署链接，因此是定位说明不齐全，并非三套完全没有主次。 |
| 应用层快照时间 SQL | 成立。warehouse.py 四处、stocktakes.py 一处；read_snapshot 已负责只读事务，可收拢取时。删除未用 list_moves 后剩四处。 |
| MCP 生命周期 | 成立。导入创建实例、lifespan 替换全局和挂载对象、routes[-1] 寻址均存在。非 lifespan 路径使用未启动的实例，但不能把不运行 lifespan 本身认定为受支持用法。SDK 的 manager 每实例仅能 run 一次，不能简单删除重建逻辑。 |
| 目录写 API | 成立。CatalogView 和 SkusView 直接拼路径及载荷，accountsApi 只有读取。 |
| 库存页重建 | 成立。App 的 key 包含 revision；InventoryView 声明但没有监听 revision。 |
| gitignore | 成立。存在重复段，无 temp/、*.log；temp/casdoor-login 约 1.2M，未被跟踪，目前由 .git/info/exclude 的 /temp/ 隐藏。 |
| 端口与个人路径 | 部分成立。当前默认 API 是 10622；prototype-status 是阶段记录，8000 包含历史事实，不应全局替换。迁移文档绝对路径成立。local-db 默认 55432，与 run-backend 默认一致，但与 .runtime/postgres/postmaster.opts 上次使用的 55438、仅 Unix socket 配置不同；监听核查未见这两个 TCP 端口，不能声称当前在线实例端口已验证。 |
| 授权重复 | 成立但非已证实漏洞。funds.post 内联检查重复；require_trusted 仅检查角色，不检查 active，不能直接替换整句。Agent 凭据授权也有各自的错误语义。 |
| 分页重复 | 部分成立。三处均有分页与筛选调度重复，但 StocktakesView 的盘点目录也是远程分页，本地记录筛选主要在盘点详情子组件。架构明确区分本地与远程记录，不应统一成一种语义。 |
| 展示工具位于 API | 成立。money、statuses、stockStatuses、today、approvalLabel，以及 accounts.kinds 属展示工具或词表。 |
| 宽类型 | 成立。Transfer.audit 迫使组件 as AuditEvent[]；StockTransfer.approval_snapshot 为 unknown。JSON 原文展示本身是 UI 选择，不能仅以 unknown 为由重做审计界面。 |
| 结算规则位置与查询 | 成立。effective 在 infrastructure 判定 posted；matched 每次扫描全部匹配，再按相关匹配取两端。可能产生重复查询，但 SQLAlchemy 身份映射会复用已加载对象，不能断言每次都新增两条 SQL。 |
| 死代码 | list_moves、stock_store.store、fundsApi.summary/preview 仓内无调用成立；对应后端 preview/summary 不能随前端封装一并删除。push-acr 无仓内引用成立，但不等于没有手动用途；部署记忆明确写撤销 Coolify 时保留 ACR 上传脚本，暂不直接删除。 |
| Schema 错位 | 成立。agent_schemas 同时包含人工凭据输入和 MCP 契约，http 导入其中人工类；是命名/归属混杂，并非跨应用层违规。 |
| 旧响应覆盖 | 成立。SettlementsView 和 useFundTransferOptions 均无结果过期判定；延迟调用只能减少请求，不能保证响应顺序。 |
| 盘点联合类型 | 成立。两类字段完全相同，detail.transfers 无法随 kind 缩窄，模板两处断言。 |

## 建议顺序与任务

### 1. 修复实际页面行为

文件：frontend/src/App.vue、views/InventoryView.vue、views/SettlementsView.vue、composables/useFundTransferOptions.ts。

- [x] 库存 key 只保留用户和身份 epoch；监听 revision 重新查询，保留筛选和页码。
- [x] 处理库存现有 busy 直接跳过刷新问题：让过期结果失效，确保刷新后的结果对应最新条件；使用组件内简单请求序号，不建通用请求协调器。
- [x] 结算查询和资金搜索在条件变化时立即更新请求序号；只有当前序号可写数据、错误与 loading。清空选择及卸载也使在途结果失效；搜索序号须在 search 调用时更新，不能等 debounce 触发。
- [x] 保留现有手动查询与筛选语义，不额外引入自动重试、缓存或后台恢复。

验收：全局刷新不清空库存筛选/页码；旧账户和旧搜索响应无法覆盖新结果。运行 npm run build；本轮不搭建前端测试环境，不做浏览器自动点击/填表。响应乱序行为若未以现有工具实测，交付时明确说明。

### 2. 明确 MCP 实例生命周期

文件：backend/entrypoints/http.py、backend/tests/conftest.py、backend/tests/test_agent_access.py；必要时局部调整 entrypoints/mcp.py。

- [x] 推荐 create_app()：每个 FastAPI 实例创建一个 MCP 实例，lifespan 通过闭包启动同一 manager，挂载通过显式引用注册；保留 app = create_app() 兼容 Uvicorn 入口。HTTP 端点可用 APIRouter 保留现有路径。
- [x] 删除全局实例替换、恢复旧实例及 routes[-1] 寻址；不新增生命周期代理或请求级动态分派。
- [x] 测试按生命周期创建新应用。现有 MCP 测试在已启动 TestClient 之外，又对同一个 app 开启嵌套 lifespan，需要同步去掉共享实例重入；不得重新启动同一 SDK manager。
- [x] 在现有 MCP 测试中覆盖独立应用先后启动、认证、发现和真实业务调用，保持人工 Cookie/MCP Bearer 隔离。

取舍：工厂需要调整路由注册和测试应用来源，但生命周期明确。保留全局并继续换挂载对象改动少，却保留本次问题，故不推荐。此项随本轮修复授权实施。

### 3. 后端局部归属整理

文件：infrastructure/store.py、settlement_store.py、stock_store.py；application/warehouse.py、stocktakes.py、funds.py、settlements.py；entrypoints/schemas.py、agent_schemas.py、http.py。

- [x] 在基础设施增加 snapshot_timestamp(snapshot) -> datetime，read_snapshot 在事务开始后取得 transaction_timestamp 并存入 snapshot.info；辅助函数只读该值，现有 read_snapshot 继续 yield Session，保留结算调用约定。
- [x] 移除应用层五处 SQL；先删除无调用 list_moves，剩余四处使用基础设施时间辅助函数。不得改成 Python 当前时间。
- [x] funds.post 复用 require_trusted，保留 active 检查；Agent 的角色比较只收拢真正等价的简单判断，不改变级别规则或错误含义，不建权限框架。
- [x] CredentialCreate/Patch 移入现有人类 HTTP schemas.py，更新导入；MCP 契约继续留在 agent_schemas.py。
- [x] 删除 stock_store 未用 store 导入。
- [x] 结算有效性判断移入 application/settlements.py。基础设施只提供匹配及两端状态的批量查询；应用在一次 overview 中计算已匹配金额索引，validate_matches 读取相关匹配后沿用同一判定。保留“任一端冲销即失效、历史保留”的规则。

取舍：结算先采用批量加载相关数据与应用层普通字典求和，符合当前规模；不为这次整理新增复杂 SQL 聚合、缓存或表。与仅移动 effective 相比，此方案消除反复扫描和逐条取端点。该职责调整随本轮修复授权实施。

验收：复用现有资金、结算、货物、Agent 测试，尤其 test_payment_and_item_reversal_invalidate_matches；仅在发现具体覆盖缺口时补简短用例。不为移动代码新增重复测试。

### 4. 前端 API 与类型整理

文件：api/accounts.ts、warehouse.ts、funds.ts、audit.ts、stocktakes.ts；相关目录、详情和盘点组件；新增少量 presentation 文件。

- [x] accountsApi 增加资金/货物账户 create、update 与 setCustody；创建类型含 kind，更新类型排除 kind。warehouse 增加 SKU create/update 的明确输入和返回类型。视图调用方法，不拼 URL。
- [x] 将金额/日期工具和各域展示词表放入 frontend/src/presentation/，更新导入。传输 DTO 与请求仍在 api/，不扩大成通用工具框架。
- [x] Transfer.audit 改为含 detail 的明确审计事件类型，去掉详情 as。approval_snapshot 用真实固定字段类型及 null；动态历史 audit.snapshot 仅约束为 JSON 值，不枚举所有审计事件形状。
- [x] 推荐在 stocktakesApi.detail 内根据已知 kind 给返回结果增加前端本地 kind，构造 {kind:'fund', transfers:Transfer[]} | {kind:'stock', transfers:StockTransfer[]}；模板按 detail.kind 缩窄。基础 Stocktake 共用一份结构，删除两个等形接口。不新增后端字段或改变 MCP 契约。
- [x] 删除未调用的 fundsApi.summary/preview 及仅为它们存在的类型/导入；保留后端端点。

取舍：本地包装足以表达盘点详情差别；后端加 kind 会扩大接口改动，没有当前必要。类型保护作用于调用处，不能声称它提供运行时响应校验。

### 5. 文档和忽略规则

文件：.gitignore、README.md、architecture.md、deploy/README.md、deploy/README.native.md、docs/prototype-status.md、docs/migrations.md；是否修改 local-db.sh 取决于默认本地配置的确认。

- [x] 合并 gitignore 重复规则，加入 temp/、*.log；不删除截图或其他本地文件。
- [x] 建议部署定位表：Compose 为首选；不使用 Docker 时 systemd 为替代；PM2 为保留的兼容备选、不推荐新部署；ACR 脚本标为手动工具、去留待确认。现有依据不足以把 systemd/PM2 全部宣布弃用。
- [x] 同步各文档定位并明确 Compose 自动迁移/备份只适用于对应发布脚本，原生方式按其独立步骤操作；不部署、不修改服务或公网代理、不接入 Coolify。
- [x] 阶段记录开头补当前默认 API 10622，历史 8000 记录标注“当时配置”，保留已执行事实。
- [x] migrations 示例移除个人路径，优先沿用项目配置；需要 socket 示例时以项目根目录 $PWD 展开，不写真实连接凭据。
- [x] local-db 保留可配置默认，文档解释 55432 默认与本机 55438/socket 覆盖。若要统一为 55438，必须联动 run-backend、socket、说明及已有运行配置，不能只替换一个数字；不自动重启数据库。

### 6. 暂缓合并分页调度

优先保留三个页面现状。本次不新建通用列表 composable；当前重复较少，且详情与目录语义不同。
若后续单独批准，最多收拢 page/limit/debounce 的相同调度，查询参数、业务筛选和本地记录计算继续各自负责。

## 集中验证与交付

- [x] 全部前端改动完成后运行 npm run build（类型检查与构建）。
- [x] 全部后端改动完成后运行 ./tools/run_tests.sh，仅 fgas_test；迁移测试使用独立临时库。不得传日常开发库、不得运行 dev --reset-db。
- [x] shell 有改动时只对相应脚本运行 bash -n；文档和全部改动运行 git diff --check。
- [x] 不运行远程发布、不扩展 CI、不自动操作浏览器。不为文案/移动文件/删除未用封装新增永久测试。
- [x] 报告实际命令、结果和未验证项。本轮已完成代码修复与集中验证，结果见下文。

## 实施结果（2026-10-24）

任务 1–5 已实施。任务 6 保持暂缓；ACR 上传脚本和本地数据库默认端口保留。没有新增数据库字段、依赖或 CI，也没有部署、提交或推送。

- `DATABASE_URL='postgresql+psycopg2://fgas@/fgas_test?host=/data/sunyunbo/www/FGAS/.runtime&port=55438' ./tools/run_tests.sh`：65 passed in 28.78s。首次沙箱内 Unix socket 连接被拒，获准后在沙箱外完成；脚本明确核验目标库为 fgas_test。
- `npm run build`：类型检查与 Vite 生产构建通过；仍有大于 500 kB 的 chunk 提示，本次不扩展拆包。
- `git diff --check`：通过。
- 后端应用/基础设施独立审阅通过；最终前端/MCP/文档审阅通过。
- 未执行浏览器自动交互或运行时响应乱序模拟；前端请求隔离通过代码审阅，构建不代表交互验收。
