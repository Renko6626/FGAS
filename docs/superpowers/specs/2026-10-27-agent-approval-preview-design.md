# Agent 待审批查询与逐笔预览

状态：已取消。用户决定沿用现有查询，让模型根据金额、数量和方向完成简单加减，不增加统一待审清单或预览 resource，以减少接口概念和上下文负担。本文件仅保留取消前的方案供参考，不作为实施授权；已完成的默认 low、权限区别及 harness 接入文档说明保留。

## 目标与已确认方向

用户同意保留现有 MCP 四工具入口，补齐完整待审批清单和逐笔影响预览，并要求细化预览范围。默认使用 low；low/high 的查询范围相同，预览不赋予审批权。公开接入指南、核心模型和完整指南已补充默认 low、权限区别和 harness 分支，本功能在这些改动上继续。

本方案推荐只列受影响端点。预览的含义是：在当前账面上，单独批准所选待审事项，会立即发生什么。不把其他待审项预先执行，不预测全部待审通过的合计，不额外假设付款、到货或后续审批。

## 方案取舍

1. 继续让模型组合现有列表、详情、余额和库存：无新增接口，但完成申请难发现，模型需自行计算，容易漏旧单或混淆阶段。
2. 在 `fgas_query` 增加完整清单与按需预览两个 resource：推荐；保持四工具、现有授权和应用分层，列表较短，预览时再计算账面影响。
3. 清单每行都嵌入预览：少一次调用，但翻清单也要计算全部端点，重复返回余额和库存；不采用。

用户已认可方向 2；以下 resource 名、字段及预览口径是本次提交审阅的具体设计。

## 预览范围

| 待审事项 | 批准后的状态 | 即时资金影响 | 即时货物影响 |
| --- | --- | --- | --- |
| 资金单 | posted | 来源余额减金额，去向余额加金额 | 无 |
| 货物主单 | in_transit | 无，关联付款不重复记账 | 组织端点在途计划量增加，正式库存不变 |
| 到货完成申请 | 申请与父单均 completed | 无 | 来源库存减少、去向库存增加，组织端点在途计划量减少 |

- 资金只列来源、去向两个账户；public/private/external 均按正式账本的借方减贷方返回。外部账户余额是账本累计，不能解释成对方的真实银行余额。
- 货物按“组织端点（public/private）× 本单 SKU”列行；无关仓库、无关 SKU 不返回。未发生过正式流水的相关组合按 0 展示。
- 外部货物端点仍在来源/去向中显示身份和方向，不返回它的库存数；系统不管理供应商实际库存。
- 同一货物预览行包含正式库存和在途计划量的 before/delta/after。即使正式库存 delta=0，也保留该项，明确货物主单批准不会立即入库。
- 沿用当前库存查询口径：在途计划量在每个参与的组织端点按正数量统计，不区分待出/待入，不是预留或可用库存扣减。主单批准为 +quantity，完成为 -quantity；正式库存按转移方向增减。
- 一笔内部调拨列出两个组织端点对应的 SKU；本期不附全社团库存总量、公账总余额、全量账户或跨单累计。
- money 使用整数分运算，同时返回元字符串；数量及数量变化用整数文本，可含负的 delta。不计算估值、成本或利润。

## MCP 契约

不新增顶层工具，不新增人工 HTTP 路由，不改数据库 schema。

### 1. `pending_approvals`：完整清单

调用：

```json
{"resource":"pending_approvals","filters":{"page":1,"limit":20}}
```

输入沿用 PageFilters 的 page/limit（默认 1/20，上限 100），另支持：

- `kind`：可选，fund_transfer / stock_transfer / stock_completion。
- `submitted_by_current_connection`：默认 false；true 仅匹配该待审事项自身的提交连接。完成申请匹配确认记录的来源，不能以父单的来源代替。

默认覆盖全部仍 pending 的事项，含人工及其他连接提交的记录，无最近 30 天限制。不套用事件查询的 `_event_filters`，不要求用户额外传 all_time。

返回现有 `api_version/data/items/page/has_more/filters/snapshot_at` 分页结构。每行提供 kind、id、parent_transfer_id（仅完成申请有值）、status、effective_date、created_at、description、来源/去向的 id/name/kind、申请人的 id/name、提交连接 id/name；资金项有 amount_minor/amount，货物项有涉及的 SKU id/name/unit/quantity。不返回整份审计、历史申请、快照或预览。

`stock_completion` 的 id 是完成申请 ID，parent_transfer_id 是父货物单 ID；日期、申请人及连接取完成申请本身，货物端点和明细取父单。已拒绝、已完成、已失效申请不入清单。清单按“待审事项”列行，与首页按父货物单计数的口径不同，不改首页计数。

三个 pending 查询 UNION ALL 后统一按 created_at 降序、kind 升序、id 降序排序并分页；数据库取 limit+1 判断 has_more。分页不承诺跨请求固定快照，正常刷新即可，不增加游标或恢复机制。

### 2. `approval_preview`：指定待审事项预览

调用：

```json
{"resource":"approval_preview","filters":{"kind":"fund_transfer","id":"待审事项ID"}}
```

输入仅 kind、id，均必填。使用 filters.id，保持现有 query.identifier 的详情分派规则不变。此接口只预览已有待审事项获批的效果，不接收任意草稿、执行动作、全部待审或未来时点参数。

返回字段：

- `snapshot_at`：本次只读数据库快照时间。
- `kind/id/parent_transfer_id`、来源/去向、说明和业务日期：识别所选事项。
- `status_before/status_after`：本次批准的状态转换。完成申请另返回 `parent_status_before/parent_status_after`，其他种类对应父单字段为 null。
- `fund_effects`：每行 account_id/account_name/kind，以及 before_minor/delta_minor/after_minor 和对应 before/delta/after 元字符串；非资金预览为空数组。
- `stock_effects`：每行 account_id/account_name/kind、sku_id/sku_name/unit，以及 `on_hand`、`in_transit_planned_quantity` 两组 before/delta/after 整数文本；非货物预览为空数组。
- `blockers`：本次复用现有业务校验发现的阻塞原因文本列表；没有发现时为空。它与连接是否拥有审批权限无关。

以下仅展示资金预览的效果行：

```json
{
  "account_id":"fund_pool",
  "account_name":"社团资金池",
  "kind":"public",
  "before_minor":100000,"delta_minor":-12000,"after_minor":88000,
  "before":"1000.00","delta":"-120.00","after":"880.00"
}
```

有 blocker 时仍可返回算术影响，但不得称为当前能够实际批准；after 和 status_after 表示假设获批的结果。不存在返回 not_found；事项已非 pending 返回 state_conflict，提示刷新。若 pending 完成申请的父单已不在途，以 blocker 说明不满足完成条件。

## 业务校验与只读保证

- 在应用层选择事项、解释状态并生成预览，基础设施只负责选取记录和读取账面数，不决定审批策略。
- 每次清单或预览复用现有 `store.read_snapshot`。单次预览的事项、余额和数量来自同一快照；不添加写锁、保存预览、请求恢复或新的快照表。
- 资金分录方向复用现有平衡转移方案，余额用现有正式 JournalLine 查询；pending 本身没有正式分录。关联冲销单时保留原有“原单仍 posted”等校验，不提前更新原单。
- 货物主单复用 `warehouse.validate(existing=True)`；批准只入在途，不提前以来源库存不足阻止主单审批。
- 完成预览复用实际完成使用的纯读取校验/数量计划。允许将 `post_completion` 内既有 validate、来源可用量校验与 build_moves 小范围收敛为 `warehouse.plan_completion(db, item)`，实际执行和预览共用；该函数不修改状态、不 flush、不写审计。不抽取通用校验框架。
- 来源组织库存不足属于现有完成业务阻塞，需明确报告。不要为本功能新加资金余额不得为负的限制，也不因账户或 SKU 已停用阻断原本允许处理的旧单。
- 不调用 approve/post/complete 后再回滚来模拟效果。预览不创建 JournalLine、StockMove、Confirmation、Audit，不改变任何业务状态。
- 查询不发起银行付款、实物交付或自动审批；快照后的状态可能变化，真正执行仍走现有审批服务重新检查。已有付款引用不产生资金影响，不级联其他单据或结算。

## 文档与交付边界

核心模型、help、完整指南补充“先查待审列表，再按需预览，并报告待审/假设获批”的最短说明。保留默认 low、harness 分支和已有输入输出 Schema 的按需加载方式。README/architecture 只同步新增查询的职责与范围，阶段记录只写实际完成和验证的内容。

本期不做批量合计、审批顺序模拟、库存预留、草稿预览、冲销/拒绝效果预览、新页面或前端审批交互，也不新增角色、存储、依赖和自动重试。需要这些能力时另行讨论实际场景。

## 验收

复用真实 PostgreSQL、人工 HTTP 准备和原生 MCP 路径的现有测试设施，覆盖三类事项、老 pending、完成申请 ID/来源、分页、受影响端点、实际审批前后数值一致、库存不足及查询不写账。只用 fgas_test；不在本轮计划阶段运行清库脚本或业务测试。详细任务及验证步骤见实施计划。
