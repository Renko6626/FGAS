# 全局待结算匹配查询

状态：用户已确认实施（“开干”），实现与集中回归已完成。与已取消的待审批/预览方案无关。

## 需求与边界

用户希望有整体接口查询尚未报销匹配的账目，并接入 MCP；关联本身仍只有 high 连接才能办理。查询需同时看见原垫付未结和已有报销付款未匹配，避免仅凭私账净余额为0误认已完成逐笔结算。

沿用现有私账结算模型，覆盖费用报销（expense）与代收交回（receipt），按方向区分；不做净额抵扣、不自动推荐或保存匹配，不增加匹配送审流程。

## 方案取舍

- 继续逐私账调用 settlement_overview：无需新接口，但模型需先查目录再逐个请求，发现全局待匹配事项较繁琐。
- 新增一个全局待匹配明细查询：推荐；一次分页查询跨私账返回未完成事项，按需复用原私账详情和 high 匹配动作。不新增顶层 MCP 工具。
- 仅新增按私账的汇总：响应更短，但要看具体付款/原支出仍需额外查询；本次不另增加汇总入口。

## 接口建议

人工 HTTP：`GET /api/settlement-outstanding`，沿用 Cookie 身份，只读。

MCP：现有 fgas_query 增加 resource=`settlement_outstanding`；low/high 均可查询。首次示例：

```json
{"resource":"settlement_outstanding","filters":{"direction":"expense","page":1,"limit":20}}
```

两入口共用 `settlements.outstanding` 应用服务；MCP 继续通过 agent_queries、agent_catalog、agent_schemas 适配，不从入口直接调用底层查询。

过滤条件：

- `account_id`：可选，仅一个私账；省略查全部私账。
- `direction`：可选，expense（垫付/报销）、receipt（代收/交回）；省略两方向均查。
- `kind`：可选，item（原收支）、payment（结算付款）；省略两侧均查。
- `page/limit`：默认1/20，limit上限100。

返回分页 items、page、limit、total、snapshot_at。MCP 额外按既有格式提供 api_version、has_more、filters，以及整数分字段对应的元字符串。日期范围不新增参数；全局未结项无默认30天窗口。

每行仅包含：

- 私账 account_id/account_name、kind、direction。
- transfer_id、effective_date、description、counterparty、来源/去向账户 id/name。
- amount_minor、matched_minor、remaining_minor；MCP 对应 amount/matched/remaining 元字符串。

本次不返回完整审计、历史匹配数组、账户余额、所有私账资料或全局金额合计。模型可按 transfer_id 读取已有资金单详情，按 account_id 查询已有 settlement_overview。

## 准确口径

- 仅返回 status=posted、reversal_of为空、剩余未匹配金额大于0的普通转移；pending/rejected/reversed 和冲销单不出现。
- item：private→external 为 expense，external→private 为 receipt。
- payment：public→private 为 expense，private→public 为 receipt。
- 只计两端均为posted的有效 SettlementMatch。部分匹配返回剩余额；任何一端冲销，仍有效一端的可匹配金额按现有规则恢复。
- 原收支未结和付款未匹配是关系的两侧，不能直接加总为“尚需报销金额”。余额为0的私账仍可能有两侧未匹配记录，必须保留。
- 停用账户的历史未结事项仍可见；显式 account_id 不存在返回404，非私账返回400，沿用已有私账查询口径。
- 一次现有只读快照内计算。复用 matched_amounts、item_account、settlement_account 及现有持久层读取，避免逐账户重复调用 overview；按 created_at降序、transfer_id降序稳定排序并分页。当前低频规模采用简单计算，不引入新汇总表、缓存或查询框架。

## 权限与写入

low/high可读范围相同；low不会因为查到匹配记录而获得写权限。匹配继续复用 high 的 `fgas_execute(settlement, match)`；已有付款不使用 create 重记。创建付款并匹配的 settlement/create 同样仍需high。

人工 HTTP 的既有匹配权限仍为管理员/受信任用户，本次不改人工角色规则；“只有high”指MCP连接等级。查询不创建转移、分录、匹配或审计，不新增数据库表/字段/迁移或顶层工具。

## 实施与验收

1. 应用层补全局只读查询，复用现有结算计算；不重写匹配算法或修改原私账 overview 响应。
2. 增加人工 HTTP 路由、MCP query resource与输入/输出 Schema、help 示例；更新指南，写明两侧不能加总及匹配仅high。
3. 复用现有测试验证多私账、部分匹配、净余额0但仍未匹配、费用/代收方向、冲销后的有效性，以及过滤/分页；原生 MCP 验证low能读但不能匹配，high仍走已有匹配动作。
4. 只在 fgas_test 运行数据库检查，集中运行现有相关测试及必要回归，不新增页面、浏览器交互或独立CI。确认查询前后业务行、分录和匹配不变。

实施进度与实际验证见对应实施计划及 docs/prototype-status.md。
