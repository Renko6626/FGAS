# Casdoor 成员准入

2026-10-29 按用户确认，仅启用 Casdoor 原生应用标签限制。FGAS 不新增网站侧标签校验，不改变 OIDC 声明、数据库或三档角色。

## 当前配置

- 认证站点：`https://auth.fantasyguide.cn`，应用 `admin/FGAS`（大小写敏感），组织 `thfg`。
- FGAS 应用 Tags 为 `fgas-member`，关闭注册和游客登录，Token 格式保留 `JWT`。
- 首批允许账号为 `thfg/Nipporita` 和 `thfg/Renko_1055`，均已添加 `fgas-member`。两人在 FGAS 中原有的管理员角色不变；Casdoor 的 `isAdmin` 均为 false。
- 组织标签依次为 `public-user`、`fgas-member`。部分注册流程会以组织第一项标签作为默认值，必须保留普通标签在前，避免公共注册自动获得成员资格。
- 组织 Account items 的 Tag 修改权限为 `Admin`；当前组织各应用注册表单均没有 Tag 项。其他应用的 Tags、默认标签及注册开关保持原值。

Casdoor 原生规则允许匹配任一应用标签的用户登录；组织管理员、全局管理员及 built-in 组织存在豁免。因此该配置用于限制普通公众账号，不作为隔离 Casdoor 管理员的边界。规则见 [Casdoor 应用标签文档](https://casdoor.ai/docs/application/tags/)。

## 开通与停用

开通成员：在 Casdoor 管理后台进入 `thfg` 用户，给 Tag 添加 `fgas-member` 并保存；已有其他标签时用逗号分隔并保留。成员随后从 FGAS 登录，首次进入仍按 FGAS 现有规则建立普通用户。需要受信任或管理员权限时，在 FGAS 的“用户权限”中另行设置。

停用成员：移除 Casdoor 用户的 `fgas-member`，并在 FGAS“用户权限”中停用该用户。只移除标签不会撤销已有 FGAS Cookie 会话或 Agent 凭据；FGAS 停用用户会撤销网页会话并阻止 Agent 访问。“强制下线”只撤销网页会话，不能代替停用。

公共网站继续使用原有注册入口。不要为公共应用设置 `fgas-member` 默认标签，不要把它移至组织标签第一项，也不要在公共注册表单开放 Tag 选择。

## 本次验证

通过现有管理凭据调用 Casdoor API，修改后重新登录管理 API 并读取应用、组织和两个用户，确认上述设置已保存；核对其他应用准入设置未变、注册表单无 Tag 项。未创建测试账号、冒用成员登录或运行浏览器交互，实际成员及非成员登录效果仍待人工体验确认。

修改前仅涉及的字段已备份至本机 `/tmp/sunyunbo/fgas-casdoor-tags-before-20261029.json`，权限 0600，不含凭据。此路径是临时回退记录，不作为持久备份承诺。此次只有 Casdoor 配置和项目说明变更，无需构建、数据库迁移或重新发布 FGAS。
