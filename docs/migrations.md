# 数据库迁移

FGAS 的 schema 只通过 Alembic 演进。`backend/migrations/versions/0001_baseline_schema.py` 是当前基线，包含全部 20 张表、索引和约束；新库和已收养的旧库都应处于该 revision 或后续 revision。

## 本地命令

```bash
# 从项目根目录执行，使用已配置的 DATABASE_URL。
# 如需手动传入，以下为本地 socket 示例，按实际主机、端口和库名调整：
export DATABASE_URL="postgresql+psycopg2://fgas@/fgas?host=$PWD/.runtime&port=55438"

# 升级到最新
.venv/bin/python -m alembic -c alembic.ini upgrade head

# 查看当前 revision
.venv/bin/python -m alembic -c alembic.ini current

# 检查模型与迁移是否漂移
.venv/bin/python -m alembic -c alembic.ini check

# 生成新 revision（先改模型）
.venv/bin/python -m alembic -c alembic.ini revision --autogenerate -m "describe change"
```

`scripts/local-db.sh` 默认使用 TCP `127.0.0.1:55432`，与 `scripts/run-backend.sh` 的默认连接一致。本机历史配置使用 `.runtime` socket 和 `55438`，不是脚本默认值；使用前核对实际配置，并通过 `FGAS_PG_PORT`、`FGAS_PG_SOCKET`、`FGAS_PG_HOST` 与 `DATABASE_URL` 保持一致。不要为迁就示例重启或重建已有数据库。

`alembic.ini` 不保存数据库连接；`backend/migrations/env.py` 依次读取调用方传入的 `db_url`、`-x db_url=...` 和 `DATABASE_URL`。

## 本次开发基线例外

2026-10-27 用户明确货物负责人统一无需处理旧数据迁移，开发阶段直接重建。0001基线已同步移除stock_accounts.member_id列，负责人只保存在既有历史表。现有同为0001的旧开发库不会通过 upgrade 自动转换该列，使用新结构前须按确认范围重建；本次只备份并重建fgas_test，未改日常fgas。没有新增旧数据回填或兼容逻辑。后续正式模型演进仍遵守下述新增revision规则。

## 新增模型变更

1. 修改 `backend/infrastructure/models.py`。
2. 生成 revision，人工检查表、列、索引、外键和 CHECK 约束；Alembic 对 CHECK/partial index 的自动比较不可靠。
3. 在独立临时库或 `fgas_test` 上执行 `upgrade head`，再跑 `alembic check`。
4. `./tools/run_tests.sh` 会执行迁移测试：upgrade、幂等 upgrade、drift check、downgrade/upgrade、约束与索引检查。
5. 删除不在版本控制中的临时库。

不要手改已应用的 revision，也不要使用 `create_all`、`scripts/upgrade-*.sql` 或手工 SQL 作为新变更路径。

## 部署与自动升级

`deploy/compose.yaml` 的 `migrate` 是一次性服务，命令为 `alembic -c alembic.ini upgrade head`；`api` 使用 `service_completed_successfully` 依赖它。`deploy/apply-release.sh` 的顺序是：

1. 启动并等待 `db` 健康。
2. 若 public 已有表，执行 `pg_dump -Fc --no-owner` 到部署根 `backups/`，保留 30 天；备份为空则中止。
3. 显式执行 `docker compose run --rm --no-deps migrate`，避免已退出的 one-shot 容器不重跑。
4. `--init-db` 时再运行 initialize 写入初始目录。
5. `up -d --wait` 启动 API 和 Web。

迁移失败时脚本退出，不启动新 API；不自动 downgrade。手工更新前应先备份并显式运行 migrate。

## 备份与恢复

- Compose 发布：自动备份到 `/opt/fgas/backups/fgas-<UTC>-pre-migrate.dump`。
- 本地/PM2：迁移前手工执行 `pg_dump -Fc`，失败不要继续。
- 恢复是手工操作，需先确认目标库、停止服务并取得明确授权；不要对正式库运行测试脚本。

## 旧库收养

基线前创建的库没有 `alembic_version`，`upgrade_schema()` 会拒绝自动建表。不可丢弃的库按以下顺序处理：

1. 备份并确认目标库。
2. 执行 `scripts/upgrade-agent-access.sql`、`scripts/upgrade-user-auth.sql`、`scripts/upgrade-posted-at.sql`。
3. 校验表、列、索引和约束与当前模型一致。
4. `alembic stamp 0001`。
5. 执行 `alembic upgrade head` 和 `alembic check`。

可丢弃的旧库直接重建：

```bash
dropdb -h "$PWD/.runtime" -p 55438 -U fgas --force fgas
createdb -h "$PWD/.runtime" -p 55438 -U fgas fgas
AUTH_MODE=development .venv/bin/python -m backend.application.initialize
```

## 并发与锁

在线迁移使用 PostgreSQL advisory lock `734622`，与业务写锁 `734621` 区分，并通过 `pg_try_advisory_lock` 在已有迁移运行时快速失败；同时设置 DDL `lock_timeout`。迁移应保持向后兼容：先扩展 schema 并部署代码，再在后续版本收缩；不要在同一发布中删除或重命名旧代码仍在使用的列。离线 SQL 不取锁：

```bash
.venv/bin/python -m alembic -c alembic.ini upgrade head --sql
```

离线 SQL 仅用于审阅，正式执行仍由 migrate 服务完成。
