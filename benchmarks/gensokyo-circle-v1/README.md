# 幻想结界同好社基准 v1

这是一套固定业务情景，用来比较不同 Agent 客户端、模型和 low/high 连接的接入及办事体验。社团、人员、商家与交易均为虚构，故事截至2026年10月27日。没有自动跑模型或自动评分平台。

`scenario.json` 定义八名联系人、一个公账、五个成员私账、32件东方主题货品，以及49笔资金单、52笔货物单。历史含六批采购、三场完整展会、成员报销和交回、分散保管、待审与取消历史。三场固定苏禾收银；宿舍保管仍计社团库存。

`tasks/` 中24张卡面可以单独交给受测 Agent。`golden.json`、`evaluator.md`、情景配置、脚本和运行目录只供准备者或评估者使用，不能随卡面交给受测 Agent。

## 本机准备

在仓库根目录运行，使用已安装项目依赖的 Python：

```bash
.venv/bin/python scripts/benchmark.py init
.venv/bin/python scripts/benchmark.py check
.venv/bin/python scripts/benchmark.py serve --port 10623
```

在 worktree 中运行时，`.venv` 如未链接，可用主仓库已有虚拟环境的 Python 执行同一脚本。脚本会从 Git common directory 找到主仓库 `.runtime`，默认使用本机 PostgreSQL 的 Unix socket 和55438端口、fgas用户。可显式传入 `DATABASE_URL` 覆盖连接参数；脚本始终把目标库改成 `fgas_benchmark`，随后核对实际数据库名。不会读取 `.env`，不输出数据库密码。

初始化会创建独立 `fgas_benchmark`，经既有 Alembic 和 development种子建表，沿人工 HTTP 入口登录、维护目录、提交和审批、完成到货、匹配结算、签发凭据。三个人工操作身份为 admin、trusted、untrusted；八个 Member 联系人与登录身份分开。admin初始化显示名为林舟财务操作身份，其余保持种子显示名。HTTP身份仅供准备者，受测者使用原生 MCP。

`init` 拒绝非空库。需要开始另一个独立任务或复测时，先停止本轮基准API，再运行：

```bash
.venv/bin/python scripts/benchmark.py reset
```

`reset` 先对 `fgas_benchmark` 做权限0600的 `pg_dump` 自定义格式备份，再删除和重建这个库。数据库仍被连接占用时会停止，要求手动停止基准服务；不杀连接、不重试、不续跑。准备失败会保留部分数据供查看，下一次请显式 `reset`。初始化、重置和核对各自启动脚本控制的临时回环API，结束后退出。不会向既有开发API灌数据，不会重启日常服务，不会改 `fgas` 或 `fgas_test`。

私有文件位于主仓库已忽略的 `.runtime/benchmarks/gensokyo-circle-v1/`：

- `credentials.json`：四枚连接及密钥，仅当前用户读写。
- `mapping.json`：本轮符号到UUID映射，仅当前用户读写。
- `backup-*.dump`：每次重置前的备份，仅当前用户读写。
- `api.log`：准备过程临时API日志。

四种连接分别为 `ordinary-low`（untrusted/low）、`trusted-low`、`admin-low`、`admin-high`。需要哪一种，就只向受测 Agent 提供该枚密钥和 `http://127.0.0.1:10623/mcp`。不要交出整个凭据文件，也不要交出人工Cookie、数据库权限或其他等级密钥。评估者所在客户端必须能访问这个本机回环地址。

需要网页查看或运行冷启动任务C01时，另开终端：

```bash
VITE_API_PROXY_TARGET=http://127.0.0.1:10623 npm --prefix frontend run dev -- --host 127.0.0.1 --port 5193 --strictPort
```

这是已有Vite代理配置，不改部署。浏览器访问`http://127.0.0.1:5193`，人工使用development登录；端口占用时可换其他空闲端口。C01只给受测Agent这个站点地址及当前low密钥，让它从页面发现公开接入指南并使用原生MCP，不预先提示/mcp路径或代装连接。已配置的任务可以直接沿用MCP地址。不要让受测Agent使用人工Cookie或/api代替MCP。

## 固定真相

目录共徽章16、立牌8、同人本8，启用28、停用4；名称包含规格，筛选用代号和标签。BAD-01-A 正式297枚：储藏室227、叶青宿舍50、临时储藏室20；另有入途120、出途10。PO-07 的960元已经支付。公账16100元。

苏禾私账余额零，但未报销及未交回各280元。陈墨原支出未结440元，已有付款尚未匹配120元，因此还需实际支付320元。周宁未报销160元。叶青300元错单已报销匹配，实际280元，留给更正任务处理。

业务日期固定在5至10月；创建、入账、负责人历史时间由实际加载产生。按展会业务日复盘必须明确使用业务日期口径。默认实际入账时间不能据此模拟系统已运行半年，不改写 `posted_at`。

`check` 经HTTP读回关键目录、余额、库存、在途、待审状态、结算、负责人历史和四种连接，与独立固定答案比较。它要求干净基线；写任务执行后的变化应按评估说明核对，不要求再次通过基线检查。不运行pytest或网页交互测试，也不代表24张Agent任务已经验收通过。
