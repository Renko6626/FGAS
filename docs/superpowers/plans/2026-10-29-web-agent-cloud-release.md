# 网页助手云端发布

用户授权提交、推送并部署至已有 Coolify 线上实例。沿用 Actions → ACR → Coolify，不改系统边界、域名、代理所有权、SSO 或持久卷，不配置真实模型 Key。

- [x] 提交并推送聊天阅读调整：`6381144`；此前公共模型设置为 `9ca63c1`。
- [x] 发布镜像安装已在隔离环境验证的 `requirements-agent.txt`，构建时执行 pip check。
- [x] Coolify 默认启用网页助手，MCP 指向容器内 10622；独立 Compose 保持默认关闭，可显式开启。
- [x] 聊天 Nginx 路由关闭响应缓冲，read timeout 300 秒。
- [x] 在原 CI 容器检查中核对助手启用、匿名访问被拒绝、模型框架可导入；不增加独立工作流或真实模型调用。
- [x] 本机集中运行已有后端检查与 Compose 配置校验。全量检查 92 passed、1 个健康接口旧版本断言失败；同步为已确认的 0002 后，该用例定向复测 1 passed。两份 Compose 校验与差异检查通过。
- [x] 手动触发既有 Build and deploy（deploy=true），等待镜像检查、ACR 上传与 Coolify 完成。
- [x] 核对迁移前备份可读、0002、容器健康、公网版本/助手开关/认证门禁及新前端资源。
- [x] 更新交付记录；不把匿名检查当作真实 Casdoor/模型验收。

发布提交 `f1bc6aa524600e8de20d00c57d651db07cb6a635`；Actions `40836820537` success，Coolify `gd8arxhtrvezg79nt4msychr` finished。备份 `/data/fgas-backups/fgas-20261029T074249Z-316627-pre-migrate.dump` 为 68100 字节、0600，归档清单可读。生产库 0002、web/API/db healthy；2 个原有用户与 0 笔资金/货物单保持。公网助手已开启，新前端资源可读，匿名助手配置/公共设置/余额、me、MCP 均 401，开发用户入口 404。未配置真实 Key 或自动操作页面，未验证真实聊天或完整恢复。
