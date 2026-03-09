# 打出「不用更新」的 iOS IPA 指南

目标：用现有证书打一个新 IPA，和安卓一样从服务器拉页面（`server.url` 已配好），以后改网站不用再打 IPA。

---

## 一、你这边已经就绪的

- **工程配置**：`capacitor.config.json` 里已有 `server.url: https://me.gaoxin.xin/baoshui/`，打出来的包会从线上加载，无需改代码。
- **构建配置**：项目根目录有 `codemagic.yaml`，Codemagic 会用它在云端 Mac 上打 iOS 包。
- **证书**：`apple_certs/cert.p12` 已存在，打包时要用到。

---

## 二、还缺什么（可能要找老板要）

| 东西 | 说明 | 你有吗 |
|------|------|--------|
| **cert.p12 的密码** | 导出 p12 时设的密码，Codemagic 填签名时要写 | 问老板 |
| **描述文件 .mobileprovision** | Apple 后台下载的、对应包名 `com.baoshui.app` 的 Distribution 描述文件 | 项目里没有，多半在老板那儿或 Apple 后台 |

如果没有 .mobileprovision，可以：
- 让老板在 [Apple Developer → Certificates, Identifiers & Profiles → Profiles](https://developer.apple.com/account/resources/profiles/list) 里，选对应 App ID `com.baoshui.app` 的 **Distribution** 描述文件，下载下来发给你；或  
- 你若有开发者账号，自己登录同上页面下载。

---

## 三、用 Codemagic 打 IPA（推荐，不需要本机 Mac）

### 1. 代码要能推送到 Git

Codemagic 是连 Git 仓库构建的。把当前项目（含 `codemagic.yaml`、`capacitor.config.json`、`ios/`、`apple_certs/` 等）推送到 **GitHub / GitLab / Bitbucket** 的某个仓库（例如 `main` 分支）。

### 2. 注册并连接仓库

1. 打开 [https://codemagic.io](https://codemagic.io) 注册/登录。
2. 点击 **Add application**，选 **Import existing project**，选中你的 Git 托管（如 GitHub），授权后选择 **baoshui 所在仓库**。
3. 选仓库后，Codemagic 会检测到 `codemagic.yaml`，用里面的 **baoshui-ios** 工作流即可。

### 3. 配置 iOS 签名（用现有证书）

1. 在 Codemagic 里打开该应用 → **Settings** → **iOS code signing**。
2. **Distribution certificate**：  
   - 选 **Upload .p12**；  
   - 上传 `apple_certs/cert.p12`；  
   - 填 **Certificate password**（问老板 p12 密码）。
3. **Provisioning profile**：  
   - 选 **Upload**；  
   - 上传从老板或 Apple 后台拿到的、包名为 `com.baoshui.app` 的 **Distribution** 描述文件（.mobileprovision）。
4. 保存。

若 Codemagic 界面里是「用 App Store Connect API Key 自动管理签名」，而你坚持用本地的 p12 + 描述文件，就选 **Manual** / **Custom** 这类选项，再按上面步骤上传 p12 和 .mobileprovision。

### 4. 触发构建

- 若 `codemagic.yaml` 里配了 `push` 到 `main`/`master` 触发：**推送一次代码**即可自动开建。
- 或到 Codemagic 的 **Build** 页，选 **baoshui-ios** 工作流，点 **Start new build** 手动开建。

### 5. 下载 IPA

构建成功后，在 **Build** 详情里打开 **Artifacts**，下载生成的 **.ipa**。

### 6. 上传到你们自己的 OTA 页

1. 打开 **https://me.gaoxin.xin/baoshui/ios-upload**  
2. 选择刚下载的 .ipa，上传  
3. 上传成功后，用户可通过 **https://me.gaoxin.xin/baoshui/download/ios-install** 安装，装好的就是「不用更新」的版本（从服务器拉页面）。

---

## 四、若用本机 Mac 打（不依赖 Codemagic）

1. 在 Mac 上克隆仓库，安装 Node：`npm ci`，然后执行 `npm run cap:sync:ios`。  
2. 用 Xcode 打开：`npx cap open ios`（或打开 `ios/App/App.xcodeproj`）。  
3. 在 Xcode：**Signing & Capabilities** 里选你的 Team，并指定用现有 **Distribution 描述文件**（包名 `com.baoshui.app`）；若 p12 在本机钥匙串，选对应证书即可。  
4. 菜单 **Product → Archive**，归档完成后在 Organizer 里 **Distribute App**，选 **Ad Hoc** 或 **Development**（仅内部分发时），导出 .ipa。  
5. 把导出的 .ipa 用上面的 **ios-upload** 页面上传即可。

这样打出来的 IPA 同样会读当前工程里的 `server.url`，和安卓一样「不用更新」。

---

## 五、小结

| 步骤 | 做什么 |
|------|--------|
| 1 | 确认/拿到 p12 密码 + 对应 `com.baoshui.app` 的 Distribution 描述文件 |
| 2 | 代码推到 Git，Codemagic 连仓库并配好 iOS 签名（上传 p12 + .mobileprovision） |
| 3 | 触发构建，下载 IPA |
| 4 | 在 https://me.gaoxin.xin/baoshui/ios-upload 上传该 IPA |

之后改网站只改服务器上的页面即可，无需再打 IPA；`server.url` 已经决定 IPA 和安卓 APK 一样「不用更新」。
