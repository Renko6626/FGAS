# 快速了解 Implementation Plan

**Goal:** 用一个前端页面讲清模型并引导 AI 使用。
**Architecture:** 独立 QuickStartView，由现有 App 导航承载；通过组件事件和助手暴露方法打开对话，业务 API 不变。
**Tech Stack:** Vue 3、TypeScript、现有 Naive UI、CSS。
**Spec:** [设计](../specs/2026-10-29-quick-start-design.md)，用户已确认单页方案。

## Constraints and review focus

不新增依赖、业务写入、存储、永久测试或浏览器自动交互。核对私账正负、普通用户与受信任用户流程区别、助手未启用情况、已有输入不覆盖、移动端与 reduced-motion。

## Tasks

交付：用户要求“实装”后，代码 `e12fd0f` 已推送并由 Actions `40851284544` 成功部署到现有 Coolify。公网版本、指南资源及匿名401检查通过，三容器healthy，schema仍0002。部署备份72413字节、0600；未做真实登录后交互或完整恢复。详情见阶段记录。

后续用户调整：增强 AI 章节权重，页首点明支持 Agent；主章节明确覆盖几乎全部日常网页业务操作，列出查询、整理、代办及完整委托示例，补齐网页助手和外部 MCP 的接入步骤。保留 low/high 审批边界及账号/连接在网页管理的说明。本次 `npm run build`、`git diff --check` 和桌面/手机只读截图检查通过，无自动点击或真实模型调用。

后续用户调整：私账示例增加“小林 → 供应商”垫付箭头；演示报销时增加“社团公账 → 小林”箭头并保留原垫付，私账归零。使用既有 reimbursed 状态，无新增状态或接口。前端重新构建和差异检查通过；桌面/手机及报销后状态的只读 fixture 截图核对无错误或横向溢出，未自动点击。

- [x] 新建 `frontend/src/views/QuickStartView.vue`：模型说明、资金/货物步骤动画、私账垫付和报销示例、AI/Agent 入口。
- [x] 修改 `frontend/src/App.vue`：快速了解导航、首页链接、助手组件 ref；修改 `FloatingWebAgent.vue` 暴露预填打开方法，不自动发送。
- [x] 执行 `npm run build`、`git diff --check`，检查实际产物与上述边界，记录阶段状态。低风险前端功能不跑后端测试。

验证记录：类型检查及生产构建通过，保留现有主 chunk 大于500kB提示；1440px、390px以及助手未启用的只读 fixture 截图无页面错误或横向溢出，已查看桌面及手机截图。截图脚本首次匹配到 `/src/api/` 模块导致加载失败，缩小为真实 `/api/` 路径后通过，与产品代码无关。未自动点击/填写或发送模型请求，未执行后端测试、业务写入、提交或部署。作者自查导航、示例正负号及不覆盖输入分支，无新增后端机制。
