# AGENTS.md

面向 AI 编码代理的协作约定。业务细节见 [README.md](README.md) 和 [architecture.md](architecture.md)，当前进度见 [docs/prototype-status.md](docs/prototype-status.md)。阶段记录和设计、计划文档可能包含已被取代的历史方案，应结合最新状态阅读；本文件保留导航和工作红线。

## 项目一句话

单社团、人民币的「资金与库存工作台」原型：以账户 + Transfer 表达资金和货物流动，含结算匹配、三档角色（管理员/受信任用户/普通用户），并通过 MCP v2（`/mcp`，Streamable HTTP）向外部 Agent 提供受控接入。薄盘点代码保留，入口暂时停用。

## 技术栈与布局

- 后端：Python 3.13 + FastAPI + SQLAlchemy + PostgreSQL。
- 前端：Vue 3 + TypeScript + Vite + Naive UI（`frontend/src/`）。
- 入口：`backend/entrypoints/http.py`（人工 HTTP，`/api`）与 `backend/entrypoints/mcp.py`（Agent MCP）。
- 分层（依赖只允许自上而下，见 architecture.md §2）：
  - `backend/kernel/`、`backend/modules/`：通用金额/数量与流水方案，不依赖 FastAPI、不认识具体业务用途，禁止被外部入口直接调用以绕过授权。
  - `backend/application/`：编排服务（funds、settlements、warehouse、stock_workflows、stocktakes、catalogs、sso、agent_* 等），负责授权、审核、状态、审计。
  - `backend/infrastructure/`：持久化、快照查询、事务、写锁，不独立决定业务策略。
  - `backend/entrypoints/`：协议适配、Schema 校验、身份解析。
- 测试：`backend/tests/`（pytest，走真实测试库和 HTTP 生产路径，Casdoor 用 mock IdP）。

## 常用命令

```bash
npm run setup      # 建 .venv、装后端依赖、前端 ci
npm run dev        # 本地开发（后端 127.0.0.1:10622，前端 5173，/api 代理）
npm run build      # 前端类型检查 + 生产构建
npm run db:init    # Alembic upgrade + 开发种子
.venv/bin/python -m alembic -c alembic.ini upgrade head   # 升级 schema
./tools/run_tests.sh   # 全部后端测试（含迁移测试）
```

## 验证红线

- 测试**只允许**运行于 `fgas_test` 库；脚本每次会重建该库的 FGAS 表。迁移测试在同一 PostgreSQL 实例上创建并删除独立临时库，不触碰共享表。**绝不**把日常开发库传给测试，绝不为跑测试运行 `--reset-db`。
- 测试使用真实 PostgreSQL + HTTP 路径，不访问外部服务（Casdoor 走 mock）。
- 前端验证 = TypeScript 检查 + 生产构建；未经用户明确要求，不做浏览器自动点击/填表，UI 至多截图。
- 永久测试围绕核心数据模型、业务约束及具体故障，不新增用例来证明入口停用、字段删除或返回结构变更；复用原核心用例并做必要适配，无独立 CI 扩展任务。

## 业务不变量（改代码前必读）

- 正式流水不可覆盖改写：错误用关联原单的冲销/更正处理，历史保留。
- 资金余额 = 借方减贷方；公账合计只计 `public` 账户；私账为正 = 成员应交回，为负 = 社团应偿还。
- 货物：批准只进在途，整笔完成才写 `StockMove` 记库存；出库不得造成组织库存负数；禁止外部账户→外部账户。
- 结算匹配不产生资金流水、不自动净额抵扣、任一端冲销后历史保留但失效、不级联冲销。
- 金额输入是元字符串、库内整数分；数量是正整数。
- 资金账户 `kind` 为 public/private/external；货物账户为 internal（实际保管，含成员长期代管）/external。类型创建后固定；停用阻止新建单、不阻止已有单处理。
- 三档角色固定；Casdoor 只负责身份，角色完全由本系统管理员维护，不从 SSO 推断权限。

## 安全红线

- `.env`、数据库连接、Agent 令牌明文**绝不提交仓库**；令牌可由所属用户登录网页后再次查看。用户已确认社团内部允许直接将 Agent 密钥粘贴到对话，由 Agent 填写本机 MCP 认证配置，无需先配置环境变量；密钥不放进业务工具参数。
- 人工 `/api` 只用 Cookie 会话；MCP 只用 Bearer 凭据；两者不可互替。
- Agent 凭据按用户确认的内部使用方案保存原文供本人再次查看，认证仍用 SHA-256 摘要；列表不返回原文，管理员也不能查看他人的密钥。外部集成必须经过应用服务与账本校验，**禁止直接写数据库或绕过授权**。

## 明确不做（第一阶段范围外）

- 不实现估值、成本、利润、订单、清点明细、请求恢复。
- 不引入微服务、队列、缓存、多主同步、通用规则引擎、幂等键/自动重试/Outbox。
- 数据库 schema 只通过 Alembic 演进：部署由 Compose `migrate` 一次性服务在 API 启动前执行 `alembic upgrade head`；迁移前必须备份，失败即停止发布。禁止用 `create_all` 或手写 SQL 作为新装/升级路径，禁止自动 downgrade。
- 历史 `scripts/upgrade-*.sql` 仅用于收养基线前旧库：不可丢弃的库必须备份、执行遗留脚本、校验 schema，再 `alembic stamp 0001`；可丢弃的旧库直接重建。
- 当前发布以 `deploy/README.md` 的 Actions → ACR → Coolify 路线为准。2026-10-28 已发布 `https://fgas.secret-sealing.club`，空库 Alembic 0001、容器健康、HTTPS、SSO 跳转与匿名 MCP 拒绝访问检查通过；真实 Casdoor 登录与首位管理员绑定、带凭据的远程 MCP、备份恢复仍待验收，附件尚未实现。首位管理员配置为 `Renko_1055`，仅使用 FGAS 专用 Casdoor 凭据；平台 push/预览自动部署关闭，发版由 `v*` 标签或手动 Actions 触发。VPS 的 `fgas-acme.yaml` 保留证书验证路径，不要删除。MCP v2 已有本机 DSH 真实模型验证；DSH 0.2.1-rc.3 普通 Web 创造模式已跑通自助安装、热加载和 low 待审提交，SDK／标准模式受限不能代表该路径。

## 已知待办线索

- 2026-10-29 用户确认 trusted/admin 可签发和使用本人的 high，普通用户仍仅 low，降为普通用户后 high 失效。网页助手默认 low，聊天工具栏或设置可手动选择本人 low/high，切换保留原生历史。网页与外部 MCP 提示词都要求 execute 先说明具体操作及影响并取得明确确认，已确认批次不反复询问；本阶段按用户要求仅作提示词约束，不新增确认状态机。用户/角色管理仍仅管理员，Agent 无相应管理工具。

- 2026-10-29 网页助手已合并到主目录 main 并发布生产，独立原型工作树已清理。助手提示词为 `docs/ai/web-agent.md`，由 `backend/application/web_agent.py` 每轮与共用 `docs/ai/overview.md` 组合；外部 MCP 仍只用原有业务说明。跨轮按框架原生消息保留工具调用、参数和结果，独立存于当前网页内存，禁止再从展示文本重建模型历史。直接启动后端默认关闭，Coolify Compose 默认开启，镜像安装 `requirements-agent.txt`，容器内 MCP 为 10622；隔离本地预览仍用专用 fgas_test，见 `docs/web-agent-prototype.md`。个人 Key/聊天未持久化；公共 Key 按用户选定 A 方案明文保存在 `web_agent_settings`，仅管理员 Cookie 管理，响应不回传，数据库优先于环境变量。

- 2026-10-29 发布代码 `f1bc6aa`，Actions `40836820537` success，Coolify `gd8arxhtrvezg79nt4msychr` finished。生产库先备份再 upgrade 0002，原有 2 个用户、0 笔资金/货物单保持；web/API/db healthy。新聊天窗口和公共模型设置资源、HTTPS、助手开启及匿名门禁已核对；没有进行浏览器自动交互、真实模型调用或全量备份恢复验收。发布记录见 `docs/superpowers/plans/2026-10-29-web-agent-cloud-release.md`。

- 2026-10-28 用户确认货物中文流程统一为“待审批 → 待完成 → 已完成”，技术值 `in_transit` 保留，对应已获批、尚未确认完成。受信任用户/管理员使用“登记转移 → 确认完成”；普通用户使用“申请转移 → 报告已完成”，报告待确认期间主单仍待完成、库存不变。主列表围绕 ST，SC 收在详情的完成记录和必要 Agent 交接中；这次仅调整文案，不改变模型、接口、权限或库存流程。

- 2026-10-27用户确认商品业务入口使用必填唯一SKU code（去空格转大写、拒绝重号），UUID只作内部关联；name合并规格，删除specification，tags表达类别/角色。公开货物明细及库存/货物/数量流水筛选用sku_code，目录查询/编辑用code。明确不做迁移/回填/旧接口兼容，直接同步0001；本轮只备份重建fgas_test并新建fgas_benchmark，日常fgas不改。东方社团基准脚本与24任务见benchmarks/gensokyo-circle-v1/README.md，不把数据加载当模型验收。

- 2026-10-27 用户要求暂停资金／货物薄盘点但保留代码：网页入口隐藏，HTTP 返回 404 并从 OpenAPI 隐藏，MCP 不再提供盘点资源；模型保留。恢复需同时启用 `backend/application/stocktakes.py` 的 `ENABLED` 与 `frontend/src/features.ts` 的 `stocktakesEnabled`，重启后端、重建前端。货物在途与完成流程继续保留；历史余额／库存默认实际入账时间，业务日期仅为明确指定的备选。前端不展示完整快照和原始审计 JSON。
- 2026-10-27 用户进一步确认删除货物完整批准／执行快照和公私分类，货物账户仅 internal/external，审计使用精简 detail。明确不新增迁移，直接备份后重建数据库并同步 0001 基线；不回填、不兼容旧结构。永久测试只覆盖核心数据模型和约束，不新增用例来证明入口停用、字段删除或返回结构变更；保留原核心测试并做必要适配。

- 成员往来当前由 `backend/application/settlements.py` 与私账实现；早期 member_claims 方案仅作历史记录，不作为当前实现入口。
- 盘点与目录已有资金、货物测试中的部分覆盖，但无独立专项测试文件；不要将其描述为完全没有覆盖。当前改进分支的集成验证为 2026-10-27 后端 84 passed、前端构建通过；真实模型定向复测与未验收项见 `docs/prototype-status.md`。
- `backend/migrations/versions/0001_baseline_schema.py` 是当前基线；未来模型变更必须新增 revision，并在 `fgas_test` 上通过迁移测试。2026-10-26 用户明确确认 Agent 密钥机制尚未正式实装，本次原文保存字段直接同步当前建库基线，不新增迁移或旧密钥兼容、回退逻辑。旧 `upgrade-agent-access.sql`、`upgrade-user-auth.sql`、`upgrade-posted-at.sql` 只用于收养旧库，处理不可丢弃的库前先问用户。

- 2026-10-27 用户明确货物负责人调整无需旧数据迁移、开发阶段直接重建：StockAccount 删除独立 member_id 存储列，统一由既有 StockAccountCustody 记录当前负责人及历史，当时 API 的 member_id/member_name 为其投影，当前公开接口已切换 member_code/member_name；同步0001建库基线，无回填/兼容。专用fgas_test重建前已备份，日常fgas未改。首次记账确认本人资料仍处于独立方案阶段，不得描述为已实现。

- 2026-10-27 当前分支已实现 MCP `me` 身份/连接等级查询、FA/SA/M/FT/ST/SC 自动业务编号、公开业务 code 契约、FT/ST/FA 网页定位、人工与已授权 high 并列交接，以及方向明确的当前库存计划与逐 SKU 汇总。历史计划为 null，内部调拨只计一次。编号只同步 `0001` 基线，未迁移旧库，日常 `fgas` 未改；定向真实模型复测结论见 `docs/ai/2026-10-27-agent-access-followup.md`，不要把旧轮结果当成新契约验收。

2026-10-27 Agent 定向复测已完成：13个最新选定场景为11通过、2回答部分符合（人工入口/权限措辞），共18轮，保留早轮反例；不代表全26场景或生产验收。版本、状态与答案分判、软件检查及基准清理见 [定向复测记录](docs/ai/2026-10-27-agent-access-followup.md)。
