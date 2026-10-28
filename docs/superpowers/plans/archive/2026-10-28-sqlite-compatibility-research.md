# SQLite 兼容性研究与实施计划草案（已归档）

> **归档于 2026-10-28，未采用。** 用户决定停止 SQLite 适配，继续使用 PostgreSQL 和 Docker Compose 部署。下文保留研究时的发现及未批准提案，均不作为当前架构、待实施计划或后续授权；不得据此实施 SQLite 支持。本次研究未修改数据库实现、迁移或部署配置。

**Goal:** 让单社团、低频使用的 FGAS 能以 SQLite 文件数据库运行，通过 systemd 部署时无需安装 PostgreSQL，同时保留现有业务规则和 PostgreSQL 使用能力。

**Architecture:** 建议保留 FastAPI、SQLAlchemy 与 Alembic，在基础设施层收敛已需要的方言差异。常规查询优先使用 SQLAlchemy 表达式；SQL 保留数据库内筛选、求和与分页，Python 组装返回明细。SQLite 的事务、编号和新装基线方案仍待确认。

**Tech Stack:** Python 3.13、SQLAlchemy 2、Alembic、Python 标准库 sqlite3，保留 psycopg2；前端仍为 Vue 3，构建环境 Node.js >=22.12。

**Spec:** 用户于 2026-10-28 要求由 Terra medium subagent 研究全部 PostgreSQL 强制依赖并计划兼容；约束来自仓库 `AGENTS.md`、用户工作约定、`architecture.md` 和当前公开业务契约。本文件中的建议尚不是已批准的设计。

## 授权与边界

- 本轮研究由三个 `gpt-6.1-terra`、`medium` 子 agent 分别覆盖模型与迁移、运行时、部署与验证，主 agent 汇总并核对实际代码。
- 没有修改数据库实现、迁移、部署配置或测试规则，没有访问真实 `.env`、连接数据库、启动服务或部署。
- 保留所有现有工作区修改；本轮仅新增本文。此前同一对话已完成的 Node 环境要求修改独立保留。
- 现有测试只允许 PostgreSQL `fgas_test` 与迁移专用临时库；SQLite 文件测试规则需要先获得批准。本轮没有运行项目测试，也没有创建 SQLite 实验库。
- 不包含 PostgreSQL 到 SQLite 的已有数据导入、业务数据重建、生产发布、全局代理变更或基准包移植。

## 核心结论

代码已经使用 SQLAlchemy ORM。跨库改造的难点是 PostgreSQL 专用 DDL、事务和查询语义，不能通过只修改 `DATABASE_URL` 或把 `text()` 换成 `func.*` 解决。

除显式报错的 SQL 外，有三处必须处理的语义差异：SQLite 的外键需要逐连接启用；现有条件唯一索引需要 SQLite 对应条件；日期时间需要统一读写 UTC。否则可能出现约束未生效、合法历史记录被禁止，或会话到期判断报错。

从当前生产代码扫描看，编号对象没有正常删除路径，目录停用、单据拒绝或取消均保留记录。可以在这一范围内设计不新增表的 SQLite 发号方式，但必须覆盖同批 ORM 插入，并在实际事务开始时取得写锁。

## PostgreSQL 依赖清单

行号按研究时的工作区记录；未来实施以函数与对象名称定位。

### 模型、编号和迁移

| 位置 | 当前依赖与影响 | 最小兼容方向 |
| --- | --- | --- |
| `backend/infrastructure/database.py:5-7` | 默认 PostgreSQL URL、通用 engine/Session 未设置 SQLite 连接行为 | 按 URL 方言配置连接；SQLite 开启外键并采用明确事务模式 |
| `backend/infrastructure/models.py:52,63,75,119,158,209` | FA、SA、FT、M、ST、SC 的 `server_default` 使用序列、`nextval/currval`、`repeat/greatest` 和 `::text` | 保留 UUID 主键与公开编号；PG 保留序列，SQLite 使用待确认的应用发号方案；SQLite DDL 不执行 PG 默认表达式 |
| `backend/migrations/versions/0001_baseline_schema.py:21-31,72-108,164-223,278-298` | 基线建立并拥有六个 PostgreSQL 序列，默认值也直接包含 PG SQL；downgrade 同样涉及序列 | 需要批准既有 `0001` 的多方言适配；PG 分支保留原行为，SQLite 建立相同业务表与约束 |
| `backend/migrations/env.py:50-64` | `SET lock_timeout`、`pg_try_advisory_lock`、`pg_advisory_unlock` 使 SQLite 在执行基线前就失败 | PG 保留迁移锁；SQLite 迁移使用其自身事务和文件锁，失败停止，不增加恢复或自动重试 |
| `backend/infrastructure/models.py:144,205-206`；`0001:143,297-298` | `postgresql_where` 仅适用于 PG。SQLite 编译会丢弃 WHERE，使负责人及完成记录受到全量唯一约束 | 同时声明对应 `sqlite_where`，保留一名当前负责人、一条待审/已完成申请和其他历史记录 |
| `models.py:19`；`0001:55` | SSO subject 的条件唯一索引同样只有 PG 条件；SQLite 的多个 NULL 本身仍可共存，此处不是同等级阻断 | 一并明确 SQLite 条件，保持声明一致 |
| `models.py` 各外键；运行与迁移 engine | SQLite 默认连接行为不能保证外键校验开启 | 每个连接启用 `PRAGMA foreign_keys=ON`，运行、初始化与迁移配置一致 |
| `models.py:7,27-28,39-40,46-47,90-91,149-150,171,196,215,232` 等 | `DateTime(timezone=True)` 的 SQLite 存取不自动保持现有 aware UTC 行为 | 使用一处简单的时间类型适配：写入规范 UTC，读出恢复 aware UTC；保留业务日期为 date |
| `backend/migrations/env.py:35` | 目前 `render_as_batch=False`；以后部分 SQLite ALTER 不能直接照 PG revision 执行 | 在具体需要重建表的 revision 中使用 Alembic batch，不默认重建所有表、不以 create_all 代替迁移 |

新建 SQLite 库必须先经过 `0001`，所以仅增加 `0002` 无法修复首个基线已不能运行的问题。多方言基线是对现有“未来改模型新增 revision”规则的一次明确决策点，不得自行沿用过去同步基线的授权。

### 事务、身份与查询

| 位置 | 当前依赖与影响 | 最小兼容方向 |
| --- | --- | --- |
| `backend/infrastructure/store.py:20` | `pg_advisory_xact_lock`；资金、货物、结算、目录、SSO 建号、部分用户/凭据维护依赖它 | SQLite 在第一次身份或业务 SQL 之前开始明确事务；不能仅删锁、使用进程内锁，或在读后原地重复 BEGIN |
| `store.py:185-197` | `REPEATABLE READ`、`SET TRANSACTION READ ONLY`、`transaction_timestamp()`；影响库存、结算、负责人详情及保留的盘点代码 | SQLite 快照复用调用者同一 Session/事务并保存 UTC 查询时间，不另外开会争锁的连接；PG 保留现实现 |
| `store.py:121-123`；`backend/application/identity.py:73-77` | 健康接口的版本读取使用 `to_regclass('public.alembic_version')` | 用绑定当前 `db.connection()` 的 SQLAlchemy Inspector 检查表，再读取版本；不能通过 engine 另取连接，避免等待自身事务；保留无版本时 None 的契约 |
| `store.py:109,116`；`backend/infrastructure/stock_store.py:58` | 人工资金、货物列表使用 JSONB 转换和包含判断；资金搜索还转换 JSONB 为文本 | 精确标签匹配保留在数据库筛选层；JSON 搜索移除不必要的 PG 强制转换 |
| `backend/infrastructure/agent_store.py:35-38` | Agent 标签筛选使用 `json_array_elements_text` | PG 使用原生 JSON 支持，SQLite 用 `json_each` 的 EXISTS；先筛选再分页，不用模糊字符串匹配代替标签成员匹配 |
| `backend/infrastructure/inventory_queries.py:4-66` | 当前/历史库存、计划、总数与 totals 使用 `timestamptz`、date CAST、`statement_timestamp()` | 用有类型的绑定参数和 SQLAlchemy CTE/聚合表达式；行、总数和 totals 在同一事务读；查询时点由 Python 提供 |
| `backend/infrastructure/dashboard_queries.py:57-68,82-96` | `jsonb_agg(jsonb_build_object(...))`、聚合内部排序及 `::text` 拼装最近货物与明细 | 数据库先选出最近 3/10 笔，再批量取这些单据的明细，Python 排序组装；不读取全量流水再分页 |
| `store.py:38`；`backend/application/agent_access.py:41` | 读出的会话/凭据日期直接与 aware UTC 比较 | 时间适配必须覆盖这些真实认证路径，不能只修库存展示 |
| `stock_store.py:92-119`；`agent_store.py:39-49`；首页和库存原生 SQL | 带偏移的筛选时间、原始查询结果类型及 Python 合并排序依赖一致日期/时间对象 | 输入统一 UTC，结果显式类型化，保证日期、UTC 时间、数量字符串与 JSON 数组契约 |

当前 `read_snapshot` 的调用者包括 `application/settlements.py:83,127`、`warehouse.py:130,135,207`、`warehouse_catalogs.py:79`、`stocktakes.py:51`。盘点虽暂停入口，仍保留其模型和已有测试。

`dashboard.py` 当前的多个查询没有另套 `read_snapshot`；兼容改造不应误称现有首页已有额外快照保证。

### 配置、部署与工具

| 位置 | PostgreSQL 绑定 | 计划处理 |
| --- | --- | --- |
| `.env.example:2`；`scripts/run-backend.sh:5-6`；`ecosystem.config.cjs:8-11`；`scripts/dev.mjs:1-7`；`scripts/init-db.mjs:1-10` | 默认 URL、缺省配置和环境加载的行为不统一；dev 与 init 入口不同 | 默认范围确认后一起调整，确保 dev/init/systemd/直接 ASGI 指向预期数据库；不把缺失 URL 默默解释成意外生产新库 |
| `backend/requirements.txt:5` | `psycopg2-binary` | 保留 PG 可选时继续保留；SQLite 使用 Python 标准库，不需要新增驱动或切异步栈 |
| `deploy/fgas.service:4,12-21`；`deploy/fgas-migrate.service:5,11-19` | PG 服务依赖；`ProtectSystem=strict` 使服务不能写项目内 SQLite 文件 | SQLite 原生路线为 API 和 migrate 配置同一 `StateDirectory=fgas`；数据库使用绝对路径 `/var/lib/fgas/fgas.db`，保持目录权限 0700 |
| `deploy/fgas-backup.service:3-14`；`scripts/backup-db.sh:4-13`；`deploy/README.native.md:155-179` | 备份恢复仅支持 `pg_dump/pg_restore` | 按数据库方言分流：PG 保持；SQLite 使用标准库 backup API 创建一致备份；恢复时停服务并核对目标 |
| `deploy/README.native.md:25-44,118-129` | 首次建库、迁移前备份及账号权限按 PG 编写 | 初始化、API、迁移、备份访问同一文件；首次 init 前准备数据目录，不能等 API 首启才创建目录 |
| `deploy/compose.yaml:5-34,71`；`deploy/apply-release.sh:33` | PG 服务、DSN、卷、健康检查和迁移前 pg_dump | 推荐第一阶段保留现有 PG Compose 路线，不通过后端 SQLite 兼容顺带重写发布系统 |
| `scripts/package-release.sh:24-31`；`.github/workflows/release.yml:51-64` | 打包 PG 镜像并检查现有 Compose | 随保留的 PG Compose 路线继续使用，不新增耗时双库云端矩阵 |
| `scripts/local-db.sh:4-12` | PG 开发实例启动工具 | 保留为显式 PG 工具；SQLite 日常开发不调用它 |
| `scripts/benchmark.py:45-116,125,338`；`benchmarks/gensokyo-circle-v1/README.md:19-29` | 强制 fgas_benchmark、PG 管理库、pg_dump、建删库和 pg_class | 首轮可延期，继续明确只支持 PG；不能因基准未移植宣称后端核心必须 PG，也不能把加载基准当跨库验收 |
| `scripts/upgrade-*.sql` | 历史 PG 基线收养脚本 | 保留历史用途，不用于 SQLite 新装，也不作为自动跨库数据迁移 |
| `README.md`、`deploy/README*.md`、`docs/migrations.md`、`architecture.md`、`AGENTS.md` | 运行要求、迁移、验证规则均描述 PG | 在批准范围内同步当前说明；历史阶段记录保留，不机械重写旧方案 |

systemd 的可写权限必须覆盖数据库所在目录及 SQLite 的 journal，若将来启用 WAL 还包括 WAL/SHM；只给主文件写权限不够。备份服务要能读取源目录，首次初始化与一次性迁移也要获得同样的目录访问权限。不要在服务运行时仅复制主 `.db` 文件作为一致备份。

### 测试设施

| 位置 | PostgreSQL 依赖 | 计划处理 |
| --- | --- | --- |
| `tools/run_tests.sh:5-16`；`backend/tests/conftest.py:23-29` | `current_database()=fgas_test` 保护、清表和初始化 | PG 保护完整保留；批准后为 SQLite 提供脚本创建的隔离临时目录/文件和显式测试标志，拒绝工作库及任意外部路径 |
| `backend/tests/test_migrations.py:14-100` | PG 临时库、pg_catalog/information_schema、`setval`、建删库及检查主键时区信息 | 保留 PG 专属验收；SQLite 用独立临时文件检查 upgrade/check、实际外键和条件唯一行为，按能力解释类型反射 |
| `backend/tests/test_funds.py:55-70,111-122` | PL/pgSQL 故障触发器 | 对 SQLite 使用简单真实触发器进行同一点故障注入，保留完整回滚断言，不改成仅验证 mock |
| `backend/tests/test_stock_transfers.py:195-211,358-374` | 货物与组合操作回滚测试使用 PG 触发器 | 同上，复用现有业务场景，不另建一套重复业务测试 |
| 现有 HTTP、MCP、Casdoor mock 用例 | 部分数据库时间和直接 ORM 创建依赖 PG 行为 | 复用真实生产路径，优先适配已有用例；新增永久用例只填 SQLite 具体风险与核心不变量缺口 |

## 不应误列为必须重做的功能

- SQLAlchemy `select/join/group_by/ilike` 本身不是强制 PG 绑定；`ilike` 的数据库大小写语义存在差别，不需要因此为中文查询引入全文搜索或 ICU。
- CTE、普通聚合、条件唯一索引并非 PostgreSQL 独有；需要改的是具体方言表达和声明。
- 当前 BigInteger 不作自增主键，不能因 SQLite 自增规则而机械替换所有金额/数量列。SQLite 的整数总和与 PG numeric 聚合范围不同，记录为范围差异，不默认新增金额算法或更宽存储方案。
- 保留 ORM 对象增删改和简单查询。不会为了“全 ORM”重写没有兼容问题的代码。
- 不重新设计角色、授权、HTTP/MCP 输出、审批状态、编号格式、冲销、结算或库存流程；不恢复盘点入口。

## 待确认的兼容方案

### 1 默认范围

| 方案 | 取舍 |
| --- | --- |
| **推荐：原生部署和新开发示例默认 SQLite，PG 保留可选，现有 Compose 继续 PG** | 直接解决朋友的 systemd 部署问题，保留已存在的发布路线；仍需维护双库核心行为 |
| 所有路线统一默认 SQLite，包括 Compose 与发布包 | 配置概念更统一，但需改持久卷、迁移、打包、备份和 CI，超出最小原生部署适配 |
| 仅支持 SQLite、移除 PG | 长期单库维护较简单，但废弃既有 PG 工具及发布能力，当前不推荐顺带实施 |

已配置的 PG URL 和已有数据库不能被默认值变更覆盖；SQLite 首轮面向空库新装，不提供已有业务数据跨库迁移。

### 2 SQLite 事务

**推荐低频起步方案：应用 engine 的实际事务统一 `BEGIN IMMEDIATE`，包括读取事务；SQLite 的 `read_snapshot(db)` 复用调用者事务。** 原 PG 事务路径保留。

这样第一次身份读取与随后授权、库存检查、发号、账本写入处于同一个受控事务，不增加 HTTP/MCP 的读写分类表或新的协调机制。代价是 SQLite 查询也争用写事务名额，慢查询会阻塞其他请求。按几人低频使用接受此取舍；不宣称支持高并发。

连接仍按第一次 SQL 惰性获取。不能在依赖函数创建 Session 时立刻抢锁，否则 Casdoor callback 内先执行的外部 token/userinfo 请求可能被纳入锁持有时间。当前 MCP 的认证事务在进入下游前退出，工具调用事务也不跨整个 Streamable HTTP 网络连接存活。

原 `read_snapshot` 另开连接的方式在此方案下会等待自身外层事务，必须同步改成 SQLite 同连接复用；退出快照不得另行提交、关闭调用者事务或清空调用者既有 Session info。`store.lock(db)` 的 SQLite 分支不再次 BEGIN，而是依赖已统一建立的事务。健康检查等元数据读取也必须绑定已有连接，不通过 engine 打开第二个事务。

备选：在各入口第一次身份 SQL 前区分读写，读用 BEGIN，写用 BEGIN IMMEDIATE。读取并发更好，但需协调 HTTP 的写请求、GET 登录回调、MCP 工具和初始化路径；在当前低频目标下暂不推荐先增加这层复杂度。

数据库繁忙或失败沿用提示、日志和人工重试；不自动重发写请求，不新增队列、请求恢复、幂等键或重试状态。迁移 engine 单独配置其外键和 DDL 事务，不盲目套用应用 engine 的事件监听器。

### 3 SQLite 编号

保留 UUID 主键以及 FA/SA/M 四位、FT/ST/SC 六位最小宽度，超宽自然扩展；编号已保存后稳定唯一，允许缺号。

**推荐在现有无正常删除的范围内先采用无新表方案：受控 Session 的 `before_flush` 按六个模型分组，读取数字后缀最大值后，为本批对象顺序分配。** 前提是同一 SQLite 写事务已 BEGIN IMMEDIATE，查询与插入、提交之间不释放锁。

必须处理同次 `add_all`、多次 flush 和待插入对象，不可给每行配置一个独立的 `max+1` 列 default：多个 default 可能在实际 INSERT 前一起计算，产生相同编号。不能用字符串 MAX，`FA-9999` 和 `FA-10000` 的字典序不是数字顺序。显式已赋编号不覆盖；正常业务输入仍不允许自定或编辑 code。

最小算法：收集 `session.new` 中已知六模型；每模型从数据库数字后缀及本批已有合法同前缀编号取上限；为 code 为 None 的对象按顺序递增赋值；使用连接查询避免递归 autoflush。PG 跳过此分配，保留序列默认值。仅给项目受控 Session 注册监听，不影响无关 SQLAlchemy 会话。

当前生产写入是正常 ORM add/flush；Core/bulk insert 不走 `session.new`，不得宣称自动覆盖这些未使用的创建入口。PG 原有直接 `Session(engine)` 的序列验收保留；SQLite 编号验收使用项目受控 Session。未来增加编号对象的其他写入方式时，必须一并纳入分配约束。

此方案每次发号需要扫描相关表的数字后缀，保留为低频规模取舍，不先建设索引字段或计数系统。回滚可能重用未提交的号；人工删库、删最高编号记录或恢复旧备份后的跨时间线不复用不在本次承诺内。

备选独立提案：新增一张六行的编号计数表，事务内更新高水位，业务行删除不会降低计数。成本是新表、Alembic、初始值和双库策略维护；旧备份恢复仍会回退高水位，不能因此包装成完整恢复方案。只有用户明确选择才新增，不因“更健壮”自动加入。

不推荐改六类表的 UUID 主键或改公开编号为随机 UUID：会扩大现有数据模型与业务契约变更。

### 4 迁移与数据

建议申请明确授权：将 `0001` 改成按方言生成等价业务 schema，PG 的表与序列行为保持；SQLite 从空文件执行同一 Alembic revision 链。基线后的真正结构变化继续新增 revision，不延伸为长期随意改基线。

本轮不迁移日常 `fgas`、不重建现有库、不自动 stamp 收养旧库。已有 PG 数据库是否与当前基线一致仍需单独核对，不能只看 revision=0001。

### 5 SQLite 环境与备份

建议最低 SQLite 3.38，且实际 Python sqlite3 连接具备所需 JSON 函数；检查 Python 所链接的 SQLite，不能仅看 shell 的 sqlite3 命令版本。版本与能力要求需写入部署说明。

先沿用 SQLite 默认 journal 模式，不为低频目标额外要求 WAL、连接队列或缓存。备份使用 Python 标准库 backup API，保留原备份命名、权限和保留天数；原生迁移更新时停止 API，备份成功后迁移，失败不启动新版本。服务保持 systemd 加固，仅开放指定数据目录。

### 6 测试规则

需明确允许由测试入口创建并持有的独立临时 SQLite 文件；拒绝把开发/部署文件或任意配置 URL 传给清表测试。PG 原有 fgas_test、迁移临时库保护保持不变。

不新增云端双库测试矩阵、浏览器交互或基准跑分工程。相关完整改动集中运行核心现有测试，局部修正仅重跑受影响检查。

## 实施任务草案

以下任务均为未开始；依赖上面的默认范围、事务、编号、基线和测试授权。任务 1 至 3 共享模型和事务约束，适合先顺序完成；不能把 schema 和编号拆给互不沟通的执行者。

### Task 1 建立双库建库与基础事务能力

**Files:** `backend/infrastructure/database.py`、`models.py`、`store.py`、`backend/migrations/env.py`、`backend/migrations/versions/0001_baseline_schema.py`；按职责新增小型 `backend/infrastructure/db_types.py` 和 `business_codes.py`；适配 `backend/tests/conftest.py`、`test_migrations.py`、`tools/run_tests.sh` 及批准后的验证规则。

**Interfaces:** 保留 `engine`、`Session`、`transaction()` 与 `read_snapshot(db)` 的调用方式；保留 ORM UUID 主键和各模型 code。增加内部 UTC 时间类型、SQLite 连接配置和已知模型的发号监听，不建立通用数据库插件框架。

- [ ] 先按批准的安全规则让测试入口生成隔离 SQLite 文件；PG 原保护不得放宽。
- [ ] 为 engine 分别配置连接与事务；运行/迁移都启用外键，应用 SQLite 采用已确认的 BEGIN 方式。
- [ ] 使 `0001` 在 SQLite 不建立 PG 序列或执行专属默认值；增加条件索引的 SQLite 声明；核对模型与迁移一致。
- [ ] 实现统一 UTC 类型与编号方案，覆盖真实开发种子的同批插入，保留 PG 现有序列行为。
- [ ] 修改 SQLite 快照复用和 schema_revision 查询，确认不会另开连接等待自身；保持提交发生在响应前。
- [ ] 适配原迁移测试：空库 upgrade、重复 upgrade、drift check、UUID/编号与实际约束；SQLite 不执行 PG catalog/setval 断言。
- [ ] 仅补必要行为缺口：同批编号及两次 flush、跨编号宽度、外键拒绝、合法负责人/完成历史可保存；复用现有权限和时间到期用例。

**Acceptance:** SQLite 空文件经 Alembic 和正式初始化路径可用；已有 PG 迁移/编号检查保留；数据库失败不留下部分正式记录。不能用 create_all 或只编译 DDL 代替真实迁移验收。

### Task 2 兼容库存、首页与列表查询

**Files:** `backend/infrastructure/inventory_queries.py`、`dashboard_queries.py`、`store.py`、`stock_store.py`、`agent_store.py`；如确有重复，仅抽取一个精确标签条件 helper；复用 `test_dashboard.py`、`test_stock_transfers.py`、`test_funds.py`、`test_settlements.py`、`test_agent_access.py`。

**Interfaces:** 保留 `inventory_page(db, params, *, page=1, limit=20)`、首页各 query 函数和列表分页返回；所有公开 code、日期/UTC、金额及数量格式保持。

- [ ] 先适配已有场景运行所需的 SQLite 故障触发器和结果类型，不删除有效断言。
- [ ] 将库存查询改为跨库类型化表达，数据库仍完成筛选、聚合和分页；历史计划维持 null，当前计划按方向汇总。
- [ ] 首页移除 PG JSON 拼装：先限定最近单据，再批量查询其明细，由 Python 保持原顺序和返回结构。
- [ ] 人工与 MCP 标签在数据库执行精确成员筛选；必要的方言差异集中在小 helper，不用 JSON 文本 contains 冒充精确匹配。
- [ ] 核对日期绑定、原生结果到 Python 的类型与时区；保留业务日期闭区间、时间窗口左闭右开、同源数量字符串。
- [ ] 集中复用已有库存、结算、标签、首页与 MCP 场景；只为未被现有用例覆盖的实际差异补小用例。

**Acceptance:** 双库在同一公开契约下返回相同业务含义；totals 对全筛选范围计算且不随页累加；内部调拨不重计、不改变非负库存或授权。

### Task 3 原生配置、数据目录与备份

**Files:** `.env.example`、`scripts/run-backend.sh`、`ecosystem.config.cjs`、`scripts/init-db.mjs`、`scripts/backup-db.sh`、`deploy/fgas*.service`、`README.md`、`deploy/README.native.md`、`deploy/README.md`、`docs/migrations.md`、`architecture.md`、`AGENTS.md`；需要时为现有备份入口增加小型 Python SQLite 备份实现。

**Interfaces:** 显式 `DATABASE_URL` 优先并保持 PG 可用；推荐原生示例为 `sqlite:////var/lib/fgas/fgas.db`，开发示例使用明确的项目数据目录；备份入口仍由 systemd timer 调用。

- [ ] 同步 dev/init/ASGI 的默认值规则，已有 PG 配置不得被覆盖；不在日常启动自动搬库或建业务目录示例。
- [ ] 为 API 和迁移单元准备相同 StateDirectory，首次 init 前显式创建目录；备份可访问源目录和备份目录，不关闭整个 ProtectSystem。
- [ ] 为 SQLite 使用一致性备份 API，PG 保留 pg_dump；统一非空检查、0600 文件与现有保留规则。
- [ ] 文档写清建库、正式 Casdoor、HTTPS、停止 API 后备份迁移、恢复目标核对和重新启动的具体顺序；不新增自动 downgrade 或恢复状态。
- [ ] 标明现有 Compose、镜像发布与东方社团基准仍为 PG 路线；不把它们宣称成 SQLite 验收。

**Acceptance:** 配置和权限适合 systemd 长期运行，SQLite 无需安装独立数据库服务。实际系统服务安装和服务器发布仍需单独授权与环境验收。

### Task 4 集中验证与交付

**Files:** 已有 `backend/tests/`、`tools/run_tests.sh` 和必要的简短 SQLite 核心差异用例；更新本计划的实际结果。

- [ ] 按批准后的测试入口执行隔离 SQLite 核心 suite；命令建议为 `./tools/run_tests.sh --sqlite`，此参数目前不存在，不可提前执行。
- [ ] 按原保护在明确指定的 `fgas_test` 上执行 `./tools/run_tests.sh`，不碰日常库。迁移检查继续使用独立目标。
- [ ] 复用真实故障注入核对资金、货物与组合操作完整回滚；只在一处补两连接真实事务争用，确认后续操作重新读取库存/状态，而非过期快照。
- [ ] 以临时源与临时恢复文件核对 SQLite 备份可恢复且业务记录一致，不使用真实业务数据；不把文件非空当恢复验收。
- [ ] 对实际修改脚本运行 `bash -n`、`node --check` 或 Python 语法检查，运行 `git diff --check`；如无前端改动不重复前端构建。
- [ ] 汇报实际命令、结果、未验收项与 PG 保留路径；不因为研究完成或测试通过宣称生产已验收。

## Review Focus

1. 身份先读后写：SQLite 第一次 SQL 即进入约定事务，权限与库存检查不在失效快照上执行；Task 1、4 负责。
2. 批量 ORM 发号：开发种子、add_all、连续 flush 不产生同号，宽度越界保持原格式；Task 1 负责。
3. 时间与标签：真实 Cookie/Bearer 到期、带偏移历史窗口、精确标签分页保持契约；Task 1、2 复用现有覆盖，补实际缺口。
4. 历史唯一性：更换负责人和多次完成申请保留合法历史，同时拒绝第二条当前有效记录；Task 1、2 负责。
5. 文件位置和恢复：初始化、API、迁移和备份使用同一目标，备份来自一致快照且能恢复；Task 3、4 负责。

## 本轮证据与资料

已执行的检查仅包括代码/脚本/配置静态读取、全仓 PostgreSQL 特征搜索和 DDL 编译，没有连接数据库。主 agent 使用已安装 SQLAlchemy 分别编译三个业务唯一索引：PG 输出包含 WHERE，SQLite 输出缺失 WHERE，证实上述静默约束问题。DDL 编译不代表迁移或业务验收。

官方参考仅用于核实数据库行为，不代表具体适配实现已验证：

- [SQLAlchemy SQLite 方言](https://docs.sqlalchemy.org/en/20/dialects/sqlite.html)：事务控制、外键、日期时间、JSON 与条件索引。
- [SQLite 隔离与 BEGIN IMMEDIATE](https://www.sqlite.org/isolation.html)：写事务串行及读事务升级限制。
- [SQLite 条件唯一索引](https://www.sqlite.org/partialindex.html)：条件索引本身可用，需要正确声明。
- [SQLAlchemy before_flush](https://docs.sqlalchemy.org/en/20/orm/session_events.html#before-flush)：普通 Session flush 事件的适用范围。
- [Python 3.13 sqlite3](https://docs.python.org/3.13/library/sqlite3.html)：内置驱动、事务控制与 backup API。
- [Alembic SQLite batch migration](https://alembic.sqlalchemy.org/en/latest/batch.html)：部分结构修改的重建方式与约束注意事项。

## 实施前需要确认

建议一起确认以下具体范围：原生与开发示例默认 SQLite、保留 PG/Compose；SQLite 事务接受查询也串行的简单方案；编号保持原格式并采用不新增表的受控批量发号；允许 `0001` 的多方言适配；允许严格隔离的临时 SQLite 文件测试；首轮仅支持空库新装。

如选择计数表、所有 Compose 默认 SQLite、迁移已有 PG 数据或更高读取并发，需先调整相应方案与范围，不能从本次研究授权推导出实施授权。
