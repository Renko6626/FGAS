# Dashboard Implementation Plan

**Goal:** 首页清楚展示公账资金、社团库存、近 7 天变化和近期转移。
**Architecture:** 现有应用/基础设施/HTTP 分层内增加只读汇总；Vue 消费单个首页响应。不改数据库、依赖或业务写入流程。
**Tech Stack:** FastAPI、SQLAlchemy、PostgreSQL、Vue 3、TypeScript、Naive UI。
**Spec:** docs/superpowers/specs/2026-10-23-dashboard-design.md（用户在对话中确认）。

## 约束与审查重点

只在 fgas_test 运行测试；不做自动浏览器交互，不扩展恢复机制。正式分录保留冲销历史；公账互转、组织仓库内部调拨不影响总量；按实际入账时间计算滚动 7 天；不同 SKU 不相加；空数据和加载中不可混为零。

## 实施

- [x] 新增 backend/tests/test_dashboard.py，走真实 HTTP 验证空数据与认证、资金冲销与周窗口、库存归属/多单位/内部调拨/在途及近期操作。
- [x] 新增 backend/infrastructure/dashboard_queries.py 执行聚合、限量近期查询；backend/application/dashboard.py 编排口径与响应；backend/entrypoints/http.py 增加 GET /api/dashboard。无 schema 修改。
- [x] 新增 frontend/src/api/dashboard.ts 类型与请求；App.vue 用汇总替代原首页零散请求；DashboardView.vue 实现资金、库存、待办、转移表与筛选，页面局部样式维持现有主题。
- [x] 将新增测试纳入 tools/run_tests.sh；运行该脚本与 npm run build，检查 diff，按需截图；记录实际结果与限制。

## 完成记录

`./tools/run_tests.sh`：62 passed（专用 fgas_test，含迁移检查）。`npm run build`：类型检查和生产构建通过，保留既有主 JS 超过 500 kB 的提示。`git diff --check` 通过。静态模拟数据截图覆盖桌面 1440px、手机 390px 和空数据，未发现页面横向溢出或运行时报错；未点击、填表或执行交互流程。截图在 `/tmp/sunyunbo/fgas-dashboard-preview/`，不作为真实业务数据或生产验收证据。未部署、未改日常库、未新增依赖或迁移。


## 紧凑布局调整

按用户反馈，压缩卡片数字、间距、最近变化与流水表行高；最近变化改为单行。库存查询按最近非零组织库存变化降序，前端仅展示前 4 种，有库存种类数仍统计全量；内部调拨不更新此排序，无接口结构或数据库变动。

验证：`DATABASE_URL=（专用 fgas_test） FGAS_TEST_DATABASE=1 .venv/bin/python -m pytest backend/tests/test_dashboard.py -q --tb=short`：3 passed，现有库存用例补充名称排序与变化排序相反、最新内部调拨不影响排序的验证。`npm run build` 通过，保留原包体积提示；`git diff --check` 通过。24 种库存模拟数据截图中只展示 4 行，桌面上方卡片约 724px → 387px，手机卡片约 332/366px，未发现页面横向溢出或运行时报错；未自动交互、未部署。
