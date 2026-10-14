# FGAS 资金与库存工作台

单社团、人民币的开发原型。以账户和 Transfer 表达资金、货物的变化；结算匹配记录成员支出报销及代收交回，薄盘点表组织普通盈亏转移。

业务模型见 [transfer-model](docs/transfer-model.md)，架构见 [architecture](architecture.md)，实际验证状态见 [阶段记录](docs/prototype-status.md)。

## 本地开发

需要 Python 3.13、Node.js 22 及 PostgreSQL。沿用现有环境和 `.env`；连接信息不要提交到仓库。

```bash
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements.txt
npm --prefix frontend install
cp .env.example .env
# 修改 .env，使 DATABASE_URL 指向本项目开发库
npm run dev
```

后端默认 `127.0.0.1:8000`，前端 `5173`，通过 `/api` 代理。当前仅支持 `AUTH_MODE=development` 的占位登录，三档角色为管理员、受信任用户、普通用户。正式 Casdoor SSO 未接入。

本轮是破坏性结构更新，没有 Alembic、旧接口别名或历史账目迁移。升级已有开发库先停止应用，然后显式重建；此命令删除 FGAS 应用表中的全部开发数据，也清理退役表，不处理其他数据库。

```bash
npm run dev -- --reset-db
npm run dev
```

普通启动只建缺少的表和初始化种子，不自动清库、不升级旧表。2026-10-15 新增 SKU 图片字段；此前已有数据库可显式执行 `ALTER TABLE skus ADD COLUMN IF NOT EXISTS avatar_url VARCHAR;`，仅加可空列，保留原数据；新库由 metadata 建立该列。种子有开发用户、公账资金池、外部收支/期初账户、公账主存放处，没有业务流水，也不为成员自动开私账。

## 账户与标签

资金表 `fund_accounts`、货物表 `stock_accounts` 共用 `id/name/kind/member_id/avatar_url/tags/active`。类型 `public/private/external` 创建后固定；联系人可空，公私分类不由联系人决定。图片为空或加载失败时显示名称首字，按名称生成稳定的浅背景、深文字配色。SKU 也保存可空 `avatar_url`，可在货物目录中维护缩略图 URL；货物账户复用同名字段。

资金公账合计只计 `public`；私账正数应交回、负数社团应偿还。货物 `public/private` 均计组织库存，外部账户不计入。联系人与实际保管人分别记录，保管交接保留历史。

标签由常用下拉选项加自定义输入组成，保存为 JSON 字符串数组，用于账户和流水筛选，不决定业务准入。停用阻止新建，不阻止已有转移处理。

## HTTP 契约

所有业务入口位于 `/api`，有效开发会话可读，目录维护、匹配和人工审批要求受信任用户或管理员。

| 路径 | 功能 |
| --- | --- |
| `/auth/users`、`/auth/login`、`/auth/logout`、`/auth/me` | 开发登录 |
| `/users`、`/users/{id}` | 管理员管理本系统用户 |
| `/members`、`/members/{id}` | 联系人目录，列表/创建/修改；不自动建账 |
| `/accounts`、`/accounts/{id}` | 资金账户列表/创建/修改 |
| `/stock-accounts`、`/stock-accounts/{id}` | 货物账户列表/创建/修改 |
| `/stock-accounts/{id}/custody` | 当前保管成员维护，`{member_id:null}` 结束保管 |
| `/skus`、`/skus/{id}` | SKU 目录，已引用后单位固定 |
| `/transfers/preview`、`/transfers`、`/transfers/{id}` | 资金转移预览/提交/列表/详情 |
| `/transfers/{id}/approve`、`reject`、`reverse` | 资金审批、拒绝、冲销 |
| `/funds/summary` | 公账合计 |
| `/accounts/{id}/settlement-overview` | 私账净余额、原收支及逐笔结算情况 |
| `/settlements` | 创建普通结算付款并匹配，`{transfer,allocations:[{item_transfer_id,amount}]}` |
| `/transfers/{id}/settlement-matches` | 向已有付款追加上述匹配 |
| `/stock-transfers`、`/stock-transfers/{id}` | 多 SKU 货物转移创建/列表/详情 |
| `/stock-transfers/{id}/approve`、`reject`、`cancel` | 货物审批、拒绝、取消 |
| `/stock-transfers/{id}/completion` | 整笔完成申请，仅 `{effective_date}` |
| `/stock-confirmations/{id}/approve`、`reject` | 完成申请审批 |
| `/stock-transfers/{id}/fund-references` | 补充已有资金引用 |
| `/stock-operations` | `{stock,money}` 一次事务创建货物和普通资金转移 |
| `/inventory`、`/stock-moves` | 正式数量查询；库存支持账户、SKU、联系人、保管人筛选 |
| `/fund-stocktakes`、`/stock-stocktakes` | 薄盘点列表/创建 |
| 上述盘点路径加 `/{id}`、`/{id}/end` | 详情/修改说明/结束 |

账户列表支持 `tag/kind/member_id`，两类转移列表支持单个 `tag`。金额输入是元字符串，数据库按整数分；数量输入为正整数字符串，数据库按整数数量。资金 Transfer 主要输入 `source_account_id/destination_account_id/amount/effective_date/description/tags/counterparty`；货物主要输入来源/去向账户、日期、说明、标签、可选单据与原单引用、多 SKU `lines` 和资金引用。

资金普通转移由可信用户自动批准过账，普通用户待人工审批。货物批准后在途，额外整笔完成才记数量；普通用户的完成申请也需审批。拒绝/取消/冲销填写原因，正式流水不能覆盖改写。货物实际账户出库不得造成负库存，两个外部货物账户间不转移。用途不再强制匹配供应商、客户或动作枚举。

## 结算与盘点

已批准的私账→外部支出可报销，外部→私账收款可代收交回。匹配归属于具体私账，与联系人无关；支持部分和多笔结算，不自动净额抵扣。匹配不产生资金流水。匹配任何一端被冲销后历史保留但失效，界面显示剩余未结或付款未匹配金额；不自动级联冲销。

盘点保存名称、说明、状态、两个专属外部账户和创建信息，不保存清点明细或独立差异账本。详情查询任一端涉及专属账户的转移及资金直接冲销。结束默认隐藏端点，仍可补录，不表示差异已结清。

## 验证

```bash
./tools/run_tests.sh
npm run build
```

测试脚本仅允许 `fgas_test`，每次集中运行先重建该测试库的 FGAS 表；不要把日常开发库传给测试。测试使用真实数据库及 HTTP 生产路径。前端验证为 TypeScript 检查和生产构建，未经要求不做浏览器自动点击/填表。

正式登录、附件、生产部署、备份恢复尚未验收，本轮不实现估值、利润、订单、清点明细或请求恢复。
