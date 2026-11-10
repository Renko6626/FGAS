# 网页助手首次使用导引 Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement this plan.

**Goal:** 让成员理解助手能做什么，并在缺少配置时找到具体下一步。

**Architecture:** 沿用 FloatingWebAgent 内的配置读取、本人凭据创建和聊天状态。只改变前端展示及就绪判断。

**Tech Stack:** Vue 3、TypeScript、Naive UI。

**Spec:** [已确认方案](../specs/2026-11-10-web-agent-onboarding-design.md)

## Global Constraints

- 不新增接口、依赖、权限或持久化；不自动选择 high。
- 不覆盖草稿、不自动发送示例、不在打开窗口时自动创建凭据。
- 按项目约定运行已有前端检查，不新增永久测试或浏览器自动交互。
- 保留工作区其他人的改动；不提交、不发布。

## Review Focus

静态核对：已有 low；仅有 high；所有连接停用；公共模型缺失；已有草稿。分别保证默认复用、手动选择、可创建 low、明确设置入口及草稿保留。

## Task 1: 首次导引与助手设置

**Files:** `frontend/src/components/FloatingWebAgent.vue`、`frontend/src/views/QuickStartView.vue`、`docs/ai/web-agent.md`。

- [x] 增加有效连接及整体就绪计算，移除首次自动弹模型设置；打开助手重新读取配置。
- [x] 主面板用业务权限摘要及模型来源；缺项在对话区解释并提供启用/配置入口。
- [x] 设置保留本人连接、模型、个人 Key，完成按钮检查整体就绪；管理员跳转既有公共设置。
- [x] 三个示例只预填，已有草稿时禁用；同步导引及提示词中的设置入口名称。
- [x] 运行 `npm run build`、`git diff --check`，检查完整差异并记录结果。

## 执行记录

2026-11-10：完成既有组件内的导引、权限摘要、助手设置与示例预填；同步快速上手与模型提示词入口名称。`npm run build`（vue-tsc + Vite）通过，保留主包超过 500 kB 的提示；`git diff --check` 通过。一次独立只读审阅未发现重要问题。未新增永久测试，未做截图、浏览器自动交互或真实模型调用，未提交或发布；未改动用户已有的 `docs/casdoor-membership.md`。
