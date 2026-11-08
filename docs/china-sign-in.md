# 为 Lit Radar 开通中国手机号、微信和 QQ 登录

三种登录方式可以分别开通。手机号由 Supabase 生成并校验验证码，腾讯云短信负责投递。微信和 QQ 通过 Authing 将平台授权结果交给 Supabase。已有邮箱用户应先用邮箱登录，在账户内绑定手机、微信或 QQ。本站用 Supabase 用户 ID 保存研究方向、收藏和已读记录。

## 手机号验证码

1. 在腾讯云短信控制台创建应用，开通中国大陆短信，准备有发送额度的账户、已审核的国内短信签名和验证码模板。模板应只有一个变量 `{1}`，用于六位数字验证码。为函数创建仅需 `sms:SendSms` 权限的访问密钥。[腾讯云短信验证码指南](https://cloud.tencent.com/document/practice/382/43070) · [SendSms 参数](https://cloud.tencent.com/document/api/382/55981)
2. 在项目的 **Authentication → Hooks** 创建 HTTP 类型的 **Send SMS** Hook，地址填 `https://rnwuzxmgxlcspvjkcppb.supabase.co/functions/v1/send-cn-sms`。生成签名密钥，将完整值存入下表中的 `SEND_SMS_HOOK_SECRET`。在 **Edge Functions → Secrets** 保存所有必填项。[项目控制台](https://supabase.com/dashboard/project/rnwuzxmgxlcspvjkcppb) · [Send SMS Hook](https://supabase.com/docs/guides/auth/auth-hooks/send-sms-hook)

| Edge Function 环境变量 | 值 |
| --- | --- |
| `SEND_SMS_HOOK_SECRET` | 此项目 Send SMS Hook 的完整签名密钥 |
| `TENCENTCLOUD_SECRET_ID`、`TENCENTCLOUD_SECRET_KEY` | 腾讯云访问密钥对 |
| `TENCENT_SMS_SDK_APP_ID` | 短信应用的 `SmsSdkAppId` |
| `TENCENT_SMS_SIGN_NAME` | 审核通过的签名原文 |
| `TENCENT_SMS_TEMPLATE_ID` | 已审核的单变量验证码模板 ID |
| `TENCENT_SMS_REGION` | 可选，默认 `ap-guangzhou` |

3. 仓库中的函数名为 `send-cn-sms`。使用 Supabase CLI 重新部署时，在仓库根目录执行下列命令。网关关闭用户 JWT 检查后，函数用 Hook 签名校验发送请求。

   ```sh
   supabase functions deploy send-cn-sms --project-ref rnwuzxmgxlcspvjkcppb --no-verify-jwt
   ```

4. 启用 Send SMS Hook 和 **Authentication → Sign In / Providers → Phone**，关闭手机号自动确认，设置验证码长度为 `6`，按站点需求设置过期时间和发送频率限制。要允许新用户通过手机号注册，还需允许新用户注册。登录弹窗会读取项目的公开 Auth 设置。Phone 已启用且自动确认为关闭时，页面会开放短信入口。用自己的大陆手机号码接收一条短信并验证，检查运营商是否实际投递。[Supabase 手机登录](https://supabase.com/docs/guides/auth/phone-login)

## 微信扫码与 QQ 登录

### 1. 在腾讯和 Authing 配置两条独立的授权路径

在 Authing 创建两个启用 OIDC 的服务端 Web 应用，例如 `lit-radar-wechat`、`lit-radar-qq`。两个应用均开启 `authorization_code`，返回类型选 `code`，选择支持公钥验证的 ID Token 签名算法（例如 `RS256`），并分别记录控制台给出的 **Issuer URL、Client ID 和 Client Secret**。每个应用只开启对应的社会化身份源，并记录其**身份源连接 ID**。[Authing OIDC 应用配置](https://docs.authing.cn/v2/guides/federation/oidc.html)

| 登录入口 | 腾讯侧准备 | Authing 侧配置 |
| --- | --- | --- |
| 微信扫码 | 在微信开放平台准备已审核、具备微信登录权限的**网站应用**。在授权回调域填 Authing 指定的域名 | 创建「PC 微信扫码」身份源，录入微信的 AppID、AppSecret，启用到微信专用应用。[微信配置说明](https://docs.authing.cn/v2/guides/connections/social/wechat-pc/) |
| QQ 登录 | 在 QQ 互联准备已审核的网站应用。在网站回调域中登记 Authing 给这个 QQ 连接生成的完整回调 URL | 创建「腾讯 QQ」身份源，录入 QQ 的 APP ID、APP Key，启用到 QQ 专用应用。[QQ 配置说明](https://docs.authing.cn/v2/guides/connections/social/qq/) |

逐项核对回调设置。微信的回调域与 QQ 的回调 URL 均取自各自在 Authing 中的连接配置。Authing 应用和 Supabase 的回调分别填写如下。

| 在哪里填写 | 登记的地址 | 谁回到哪里 |
| --- | --- | --- |
| 两个 Authing 应用的「登录回调 URL」 | `https://rnwuzxmgxlcspvjkcppb.supabase.co/auth/v1/callback`（与 Supabase 创建提供方时显示的 Callback URL 核对） | Authing → Supabase |
| Supabase **Authentication → URL Configuration** 的 Site URL 和允许的 Redirect URLs | `https://mhl533.github.io/lit-radar/` | Supabase → 本站 |

### 2. 在 Supabase 创建两个登录提供方

1. 打开 **Authentication → Sign In / Providers → New Provider**，选择 **Auto-discovery (OIDC)**。创建 `custom:wechat` 和 `custom:qq`，分别填入对应 Authing 应用的 Issuer URL、Client ID、Client Secret。使用 `openid` scope，保留默认的 PKCE 和 nonce 校验。配置 `email_optional: true`，允许用户无需提供邮箱即可登录。[Supabase 自定义登录提供方](https://supabase.com/docs/guides/auth/custom-oauth-providers)
2. 在两个提供方各自的 `authorization_params` 中把 `ext_idp_conn_id` 设为对应的 **Authing 身份源连接 ID**。例如微信项填 `{"ext_idp_conn_id":"<微信连接 ID>","prompt":"login"}`，QQ 项则使用 QQ 连接 ID。`prompt=login` 用于要求重新认证。核对两个入口在同一浏览器中也会进入各自平台。[Authing OIDC 授权请求参数](https://api.authing.cn/openapi/v3/authentication/) · [Supabase 授权参数](https://supabase.com/docs/guides/auth/custom-oauth-providers#authorization-params)
3. 配置 Authing 在已签名的 ID Token 中返回稳定、不可由用户修改的 `sub`。身份凭据取自授权平台，昵称仅用作显示。没有经过验证的邮箱时，省略邮箱声明。检查 ID Token 和 UserInfo 的实际返回字段。Supabase 可能会按相同邮箱自动关联身份，应避免转发用户自行填写的邮箱。已有账户应在登录后主动绑定。[Supabase 身份绑定](https://supabase.com/docs/guides/auth/auth-identity-linking)
4. 启用两个提供方，在 Supabase Authentication 的登录设置中开启 **Allow manual linking**。在测试页面的 `config.js` 中设置已启用的公开标识，验证后再发布到主站。两个标识默认均为空，若只开通一种，另一项继续留空。

   ```js
   // window.LR_CONFIG 中的字段
   socialProviders: {
     wechat: "custom:wechat",
     qq: "custom:qq"
   }
   ```

腾讯的应用密钥仅存放在 Authing 身份源配置中，Authing 的客户端密钥仅存放在 Supabase 登录提供方配置中，短信密钥存放在 Edge Functions Secrets 中。`config.js` 会公开发布到 GitHub Pages。

## 发布前验收

- **手机号**　用大陆手机接收真实短信，测试正确码可以登录、错误码无法登录。退出后再次使用同一号码，确认 Supabase Users 中仍是原用户 ID。另用已有邮箱测试账户在账户内绑定一个未注册的手机号，确认手机登录后仍能看到同一账户的资料。
- **微信与 QQ 新用户**　用两组独立测试身份，分别从微信入口扫码、从 QQ 入口完成授权。核对最终回到本站并可选择研究方向，账号详情中显示与入口匹配的身份。用中国大陆用户实际使用的网络分别访问站点、授权页并完成回跳。
- **已有邮箱用户**　用测试邮箱登录，先选择一个研究方向并收藏一篇论文。在 Supabase Users 中记下用户 ID，再从本站账户内绑定一个尚未注册本站的微信。退出，在新浏览器中用微信登录，核对 ID、研究方向和收藏。再按相同步骤测试 QQ。`profiles.id` 和 `marks.user_id` 应始终等于原邮箱账户的 ID。
- **取消与冲突**　取消平台授权后确认原账户仍可使用。用已属于另一个测试账户的身份尝试绑定，确认绑定失败，两边账户各自保留原资料。
