# AGENTS.md

面向 AI 编码代理的协作约定。业务细节以 [README.md](README.md)、[architecture.md](architecture.md)、[docs/prototype-status.md](docs/prototype-status.md) 为准；本文件只做导航和红线说明，与文档冲突时以文档为准。

## 项目一句话

单社团、人民币的「资金与库存工作台」原型：以账户 + Transfer 表达资金和货物流动，含结算匹配、薄盘点、三档角色（管理员/受信任用户/普通用户），并通过 MCP v2（`/mcp`，Streamable HTTP）向外部 Agent 提供受控接入。

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
- 生产部署以 `deploy/README.md` 的 Docker Compose 路线为准；真实 Casdoor、HTTPS、生产发布及备份恢复尚未验收，附件尚未实现；MCP v2 已有本机 DSH 真实模型验证；DSH 0.2.1-rc.3 普通 Web 创造模式已跑通自助安装、热加载和 low 待审提交，SDK／标准模式受限不能代表该路径。远程 HTTPS 及其他客户端仍待联调——不要把开发环境行为当作生产已验收。

## 已知待办线索

- 2026-10-27 用户要求暂停资金／货物薄盘点但保留代码：网页入口隐藏，HTTP 返回 404 并从 OpenAPI 隐藏，MCP 不再提供盘点资源；模型保留。恢复需同时启用 `backend/application/stocktakes.py` 的 `ENABLED` 与 `frontend/src/features.ts` 的 `stocktakesEnabled`，重启后端、重建前端。货物在途与完成流程继续保留；历史余额／库存默认实际入账时间，业务日期仅为明确指定的备选。前端不展示完整快照和原始审计 JSON。
- 2026-10-27 用户进一步确认删除货物完整批准／执行快照和公私分类，货物账户仅 internal/external，审计使用精简 detail。明确不新增迁移，直接备份后重建数据库并同步 0001 基线；不回填、不兼容旧结构。永久测试只覆盖核心数据模型和约束，不新增用例来证明入口停用、字段删除或返回结构变更；保留原核心测试并做必要适配。

- 成员往来当前由 `backend/application/settlements.py` 与私账实现；早期 member_claims 方案仅作历史记录，不作为当前实现入口。
- 盘点与目录已有资金、货物测试中的部分覆盖，但无独立专项测试文件；不要将其描述为完全没有覆盖。最新集中验证为 2026-10-27 后端 74 passed、前端构建通过，范围与未验收项见 `docs/prototype-status.md`。
- `backend/migrations/versions/0001_baseline_schema.py` 是当前基线；未来模型变更必须新增 revision，并在 `fgas_test` 上通过迁移测试。2026-10-26 用户明确确认 Agent 密钥机制尚未正式实装，本次原文保存字段直接同步当前建库基线，不新增迁移或旧密钥兼容、回退逻辑。旧 `upgrade-agent-access.sql`、`upgrade-user-auth.sql`、`upgrade-posted-at.sql` 只用于收养旧库，处理不可丢弃的库前先问用户。

- 2026-10-27 用户明确货物负责人调整无需旧数据迁移、开发阶段直接重建：StockAccount 删除独立 member_id 存储列，统一由既有 StockAccountCustody 记录当前负责人及历史，API 的 member_id/member_name 为其投影；同步0001建库基线，无回填/兼容。专用fgas_test重建前已备份，日常fgas未改。首次记账确认本人资料仍处于独立方案阶段，不得描述为已实现。
