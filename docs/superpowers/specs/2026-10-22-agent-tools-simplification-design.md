# FGAS MCP 工具精简方案

日期：2026-10-22。状态：用户已确认四入口及直接替换旧工具名，代码已实现；完整数据库验收受当前沙箱限制，实际证据见阶段记录。补充要求：顶层指南解释核心模型与设计思路；通过随初始化提供的 overview.md 落实。

## 1. 目标与范围

用户希望外部 Agent 和未来网页 AI 都方便使用，先把现有 Agent 接入做顺手；本轮明确要求参考同行 MCP 与主流 coding agent，系统性精简工具。当前 low 暴露 20 个工具，high 暴露 50 个。重点是减少选择负担、首次声明体积和重复说明，保留已有业务能力。

推荐外部接口改为 4 个 MCP 工具，low 可见 3 个，high 可见 4 个；对象与动作由参数表达，具体参数说明按需读取。沿用 FastAPI、官方 MCP SDK、Pydantic、现有业务服务、Bearer 与 low/high 权限。用户已确认该对外接口调整，替代旧设计中“一业务动作一个工具”的要求。

本次不增加网页聊天、模型供应商接入、服务端 JS/Python 执行、SQL 执行、批量写入协议、自动重试、工作流或新的数据库字段。此前审查提到的配置向导、单据直达链接和新查询条件另行排序，不混入本次精简。

## 2. 参考资料与结论

以下为 2026-10-22 实际读取的一手资料；推荐方案是对 FGAS 的工程判断，并非这些产品统一采用了相同接口。

| 来源 | 核实的做法 | 对本项目的启发 |
| --- | --- | --- |
| [Anthropic：Writing effective tools](https://www.anthropic.com/research/writing-tools-for-agents) | 不建议简单逐个包装原 API；可以合并相近工作，减少无关结果，提供可修正的错误说明 | 工具面向使用任务，合并列表/详情与同类目录，保留明确效果 |
| [Claude Code：MCP tool search](https://code.claude.com/docs/en/mcp#scale-with-mcp-tool-search) | 按需加载 MCP 定义；服务说明应简洁且解释能力 | FGAS 自身也保持小入口与按需说明，不要求用户的客户端具有特定发现能力 |
| [OpenAI：Tool search](https://developers.openai.com/api/docs/guides/tools-tool-search) | 将工具定义延后加载，推荐清楚的能力分组；发现有额外步骤 | 不能只把所有 Schema 移进一个巨大联合类型；应减少初始上下文 |
| [Codex：配置参考](https://developers.openai.com/codex/config-reference) | 文档列出 Code Mode 与 namespace 控制，且标为开发中的可选能力 | 编程式组合是可参考方向，但不据此假设所有 Codex 环境默认支持 |
| [OpenCode：Tools](https://docs.opencode.ai/docs/tools/) | shell/read/grep 等参数化通用工具；LSP 用 operation 参数选择多种操作 | 同类能力可以通过参数选择，不需要每个动作一个工具 |
| [Cloudflare：Code Mode MCP patterns](https://developers.cloudflare.com/agents/model-context-protocol/codemode/) | 单 code 工具或 search/execute，执行代码在隔离 Worker 中运行 | 借鉴按需说明和精简入口；本项目暂不承担代码沙箱的部署与维护成本 |
| [GitHub：配置工具集](https://docs.github.com/en/copilot/how-tos/copilot-in-your-ide/customize-copilot/extend-copilot-with-tools-and-context/configure-toolsets) | 按工具集及具体工具控制暴露范围 | 行业方案也包括分组和选择，并非一律变成单个万能工具 |

### 可行方案

| 方案 | 优点 | 代价 | 建议 |
| --- | --- | --- | --- |
| 按业务分组，low 约 10 个、高权限另加若干工具 | 参数可完整放在每个工具 Schema 中，较少依赖帮助调用 | 首次仍携带较多定义，后续操作增加时容易继续增长 | 保守备选 |
| 4 个参数化入口，按需读取精确参数 | 工具数量稳定、兼容普通 MCP、保留原服务验证 | 首次办理不熟悉的操作需额外 help；嵌套数据由服务端精确校验 | 推荐 |
| search + execute，模型编写代码 | 可在一次执行中编排多步和处理结果 | 要新增隔离运行时与执行边界，不符合本项目当前规模 | 暂缓 |

工具数减少不自动证明任务成功率、调用次数或 token 成本改善。参数化入口与按需说明须一起完成；不把 50 份 Schema 填进一个工具。

## 3. 四个公开工具

| 工具 | 输入外壳 | 作用 | 可见等级 |
| --- | --- | --- | --- |
| `fgas_help` | `topic`，可选 `resource`、`action` | 简短使用说明、当前权限、能力索引；按对象和动作返回精确契约及示例 | low/high |
| `fgas_query` | `resource`，可选 `identifier`、`filters` | 所有现有业务读取；支持详情的对象有 identifier 查详情，无 identifier 查列表 | low/high |
| `fgas_propose` | `resource`、`data` | 提交资金转移、货物转移或完成申请，固定待审 | low/high |
| `fgas_execute` | `resource`、`action`、`data` | 直接办理现有高权限业务 | high |

保留 propose/execute 两个入口，因为二者效果不同，方便客户端分别放行或提示。high 调 propose 仍然待审；low 调 execute 必须拒绝，不能仅依赖发现时隐藏。工具权限仍每次从服务端真实连接解析。

`resource`、`action` 是固定枚举，`filters`/`data` 为 JSON 对象。公开外壳只声明这些路由字段及简短说明；具体字段按下文的固定表路由到原 Pydantic 输入模型。允许对象外壳不意味着业务可以接收任意字段：每个目标都使用 `extra='forbid'` 的精确 Schema。

### help 行为

- `topic` 为 `overview`（默认）、`guide`、`query`、`propose`、`execute`。
- 默认返回当前等级、API/指南版本、三或四个入口、简短能力索引和关键效果说明，不自动返回整篇指南与全部 Schema。
- `guide` 显式返回业务指南。overview 与服务器 instructions 必须自足地表达最重要规则：只办理用户交代事项、先查真实对象、不猜 ID、金额用元字符串、待审不生效、货物创建仅在途、付款与到货独立、未知结果先查记录、用户已说明的信息不重复确认。
- 选择 query/propose/execute 且未指定 resource 时，返回该入口可用对象/动作的一行说明索引。
- 选择 query/propose/execute 并指定 resource 后，返回该对象对应的准确输入 Schema、结果字段说明及一个参数示例；execute 还必须指定 action，多种动作时先返回该对象动作索引。
- query 的帮助同时说明其支持的列表过滤与是否支持 identifier 详情；不新增当前不存在的详情能力。
- 无效组合返回字段级提示及正确的 help 参数。low 的 overview/help 不列出可执行高权限契约；显式索取 execute 契约返回权限不足。
- 帮助无会话状态，不需要启用工具组，也不要求调用者每次读完指南才能执行。已知准确参数时可以直接调用。

### query 行为

`filters` 默认为空对象。仅资金转移、货物转移、资金盘点、货物盘点支持 identifier 详情模式。详情调用允许省略 filters 或传空对象，传非空 filters 返回错误，防止静默忽略。其他 resource 不能传 identifier，按现有过滤参数查找。分页、日期含义及结果内容沿用现有服务。

### 写入行为

`data` 复用现有字段名和格式；需要 ID 的动作继续使用 `data.identifier`。不提供 upsert，不根据是否找到对象暗中切换创建/修改。Patch 继续区分省略和显式 null。业务日期不自动补今天。

每次写入处理一项现有动作，沿用现有事务。原有钱货联建、结算多笔 allocations、货物多 SKU lines 均继续支持；不增加通用批量执行数组或新事务规则。

## 4. 完整能力映射

下列旧工具名省略 `fgas_`。这是 50 个原工具的覆盖清单，保留原有权限与业务效果。

### 原上下文：1 → help

`get_context` → `fgas_help(topic='overview')` 加 `fgas_help(topic='guide')` 按需读取。默认 overview 不重复附上全文。

### 原查询：16 → query 的 12 类对象

| query.resource | 原工具 | identifier 详情 |
| --- | --- | --- |
| `fund_accounts` | list_fund_accounts | 不支持 |
| `stock_accounts` | list_stock_accounts | 不支持 |
| `skus` | list_skus | 不支持 |
| `members` | list_members | 不支持 |
| `fund_balances` | get_fund_balances | 不支持，原 account_id 仍在 filters |
| `inventory` | get_inventory | 不支持 |
| `fund_transfers` | list_fund_transfers / get_fund_transfer | 支持 |
| `stock_transfers` | list_stock_transfers / get_stock_transfer | 支持 |
| `stock_moves` | list_stock_moves | 不支持 |
| `settlement_overview` | get_settlement_overview | 不支持，必填 filters.account_id |
| `fund_stocktakes` | list_fund_stocktakes / get_fund_stocktake | 支持 |
| `stock_stocktakes` | list_stock_stocktakes / get_stock_stocktake | 支持 |

使用固定对象枚举保留资金和货物的可辨识名称；模型选择 resource 后再取得该类型实际支持的参数。不存在金额/说明筛选时明确告知，不在精简中偷偷新增查询语言或扩大过滤能力。

### 原提议：3 → propose 的 3 类对象

| propose.resource | 原工具 | 效果 |
| --- | --- | --- |
| `fund_transfer` | propose_fund_transfer | pending，无资金分录 |
| `stock_transfer` | propose_stock_transfer | pending，无数量流水 |
| `stock_completion` | propose_stock_completion | 完成申请 pending，父单不自动完成 |

### 原高权限操作：30 → execute 的对象/动作组合

| execute.resource | action → 原工具 | 数量 |
| --- | --- | ---: |
| `fund_account` | create → create_fund_account；update → update_fund_account | 2 |
| `stock_account` | create → create_stock_account；update → update_stock_account；set_custody → set_stock_custody | 3 |
| `sku` | create → create_sku；update → update_sku | 2 |
| `member` | create → create_member；update → update_member | 2 |
| `fund_transfer` | create → create_fund_transfer；approve → approve_fund_transfer；reject → reject_fund_transfer；reverse → reverse_fund_transfer | 4 |
| `stock_transfer` | create → create_stock_transfer；approve → approve_stock_transfer；reject → reject_stock_transfer；cancel → cancel_stock_transfer；complete → complete_stock_transfer；link_fund → add_stock_fund_reference | 6 |
| `stock_completion` | approve → approve_stock_completion；reject → reject_stock_completion | 2 |
| `settlement` | create → create_settlement；match → add_settlement_matches | 2 |
| `stock_operation` | create → create_stock_operation | 1 |
| `fund_stocktake` | create → create_fund_stocktake；update → update_fund_stocktake；end → end_fund_stocktake | 3 |
| `stock_stocktake` | create → create_stock_stocktake；update → update_stock_stocktake；end → end_stock_stocktake | 3 |
| 合计 | 固定组合，不接受其他配对 | 30 |

action 总共 11 个：create、update、set_custody、approve、reject、reverse、cancel、complete、link_fund、match、end。客户端工具 Schema 不展开这 30 种完整参数模型，帮助才按具体配对返回。

`stock_transfer.complete` 的 identifier 指父货物单；`stock_completion.approve/reject` 的 identifier 指完成申请。这一区别写在对应帮助和示例中。资金 approve/reject 保留 expected_version。

## 5. 使用示例

以下只说明契约，ID 是占位符，不是可直接提交的数据。

查账户，然后直接使用已知查询方式：

```json
{"tool":"fgas_query","arguments":{"resource":"fund_accounts","filters":{"q":"公账","active":true}}}
```

只看一笔资金记录：

```json
{"tool":"fgas_query","arguments":{"resource":"fund_transfers","identifier":"actual-transfer-id"}}
```

模型第一次办资金提议时按需查参数：

```json
{"tool":"fgas_help","arguments":{"topic":"propose","resource":"fund_transfer"}}
```

用户已明确业务事实后直接提交，不增加一轮强制确认：

```json
{
  "tool":"fgas_propose",
  "arguments":{
    "resource":"fund_transfer",
    "data":{
      "source_account_id":"actual-source-id",
      "destination_account_id":"actual-destination-id",
      "amount":"120.50",
      "effective_date":"2026-10-22",
      "description":"用户已说明的实际用途"
    }
  }
}
```

获授权的 high 创建同一类资金记录时使用 execute、resource=fund_transfer、action=create、相同 data。用户希望送审时仍用 propose。

高权限改账户名：

```json
{"tool":"fgas_execute","arguments":{"resource":"fund_account","action":"update","data":{"identifier":"actual-account-id","name":"用户指定的新名称"}}}
```

## 6. 实现边界与结果

MCP 适配层维护一张明确的契约表：入口/对象/动作 → 输入模型、输出模型、既有应用函数、说明与示例。help、调用校验和分派共用它，避免分别维护三份不一致的清单。可放在 `backend/entrypoints/agent_catalog.py`，只承担 MCP 适配，不做插件注册、动态导入或通用执行框架。

依赖方向仍为 entrypoints → application → infrastructure/kernel。应用层不导入契约表或 MCP。复用现有 agent_queries、agent_operations 与底层服务；可以合并完全重复的适配辅助函数，不能为减少函数数量重写账本。

执行先解析身份、检查公开入口和对象/动作，再用对应 Schema 验证，最后调用固定函数。禁止根据用户字符串做任意 getattr、导入、eval、SQL 或 HTTP 路由透传。现有每个高权限应用函数的 require_high 继续保留。

公开 outputSchema 只声明简短的稳定结果外壳，不展开所有业务结果的巨大联合类型；具体输入/输出仍由选中操作的模型在服务端验证。保留 structuredContent 与兼容文本结果。对应业务 data 保留原有 ID、状态、ledger_effect_applied、approval_required、分页、精确金额与来源字段，调用者不需为同样结果再读一整份详情。

参数错误返回 code/message，加上字段路径、可理解的原因和可直接使用的 help 参数；不回显全部用户输入，不统一吞掉字段错误。业务冲突仍沿用原服务消息；返回结构校验错误与输入校验错误分开，不能把服务端结果问题说成用户参数错了。不给未确定写入自动重试提示。

readOnlyHint：help/query 为 true，propose/execute 为 false。execute 含多类动作，声明按保守副作用处理，不将其标成幂等或只读；服务端权限是实际边界。

## 7. 迁移方案（已确认）

新 MCP 契约 API 版本设为 2。原有业务数据与 Bearer 凭据、/mcp 地址保留。移除 50 个旧公开工具名，不同时提供新旧两套，也不留下长期隐藏别名分派。旧名调用返回清楚的迁移提示，指向 fgas_help；旧名不能执行写入。

这会使固定调用旧工具名的脚本需要更新。普通 MCP 客户端需重新发现工具，缓存旧清单的会话需重连。当前仓库文档标注未正式发布，但不据此推断外部无人使用：该破坏性工具命名变更是本次明确提请用户确认的一部分。

同步更新 docs/ai/guide.md、README.md、architecture.md、现有 MCP 测试及阶段记录。旧历史设计/计划不改写为仿佛当时已采用新接口，添加被新方案替代的说明即可。

## 8. 验证与当前证据

### 已完成的只读核对

- 对照实际字典与应用函数确认 16 查询 + 3 提议 + 30 高权限操作 + 1 context = 50，low 子集 20。
- 使用 `.venv/bin/python` 导入 agent_schemas，按 `json.dumps(..., ensure_ascii=False, separators=(',', ':'))` 累加每项 Schema 字符数：low 输入 10,425、输出 52,248；high 输入 24,287、输出 89,744。指南 5,031 字符。
- 这些是未计名称/说明等外壳的 Schema 字符数，非 token 数，非实际模型上下文用量；客户端可能裁剪或按需加载。
- 尝试按 MCP SDK Tool 对象统计时当前 `.venv` 缺少 mcp，未安装依赖；随后独立导入 Pydantic Schema 完成统计。未连接数据库，未运行产品测试，未改客户端配置。
- 独立只读设计审阅用 AST 核对 16 查询与 33 写入的映射，确认加上 context 后 50 项无遗漏；检查了 high 授权、事务、Patch 与接口迁移边界，未发现需要额外澄清的实施决策。此结果是设计审阅，不是产品运行验收。

### 确认后实施的必要检查

- 复用现有真实 PostgreSQL 测试，更新原 MCP 协议用例为 low 3/high 4；检查帮助只返回所选契约、query 列表/详情、propose 固定待审、high execute 生效与来源、low 不能猜调用执行、Patch 省略/null、字段错误。合适的用例原地调整，不为每个别名复制业务测试。
- 对 50 项映射做一次性覆盖核对；选取资金提议、货物创建/完成、目录修改和结算匹配验证实际分派结果，沿用已有业务用例。未知资源/动作及错误组合在入口边界用简短参数化用例覆盖。
- 最终集中运行 `./tools/run_tests.sh`，只可指向 fgas_test。安装现有 requirements 中缺失的依赖属于恢复既定环境，不升级 SDK 或增加运行时；如果环境阻止运行，明确报告。
- 按同一序列化口径比较新旧 tools/list 输入与输出 Schema 体积；报告数字，不将声明减小等同于实际使用效果。检查帮助响应不会默认附上全部契约。
- 使用官方 SDK 检查实际发现和调用。现有外部客户端若可用，用隔离测试数据做一次发现/读取核对；不改个人长期连接配置。不引入全客户端测试矩阵或模型评测平台。
- 用户实际使用后的成功率和追问次数仍需体验反馈；协议测试通过不冒充模型自主完成业务的验收。
- 本轮不改前端时无需重复前端构建、截图或浏览器流程测试。

## 9. 已确认的决策

用户已整体批准：四个固定入口 + 按需参数说明；保留全部现有业务能力及权限；直接替换未发布草案的旧 MCP 工具名，API 版本升为 2。用户补充：顶层指南要先讲清核心模型和设计思路，已纳入随初始化提供的 overview.md。

如果用户选择保守分组方案，需重新确定高权限工具清单；如果选择真正代码执行，则另行设计运行时、部署与权限边界，本方案不视为授权。
