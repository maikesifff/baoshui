# 云 Mac 构建 iOS 安装包

使用云 Mac 服务在无 Mac 环境下构建可在 iPhone 上安装的 IPA。

## 方案一：GitHub Actions（推荐，免费额度）

### 1. 将项目推送到 GitHub

```bash
cd /opt/baoshui
git init
git add .
git commit -m "init"
git remote add origin https://github.com/你的用户名/baoshui.git
git push -u origin main
```

### 2. 自动构建

项目已包含 `.github/workflows/build-ios.yml`，推送后会自动触发构建。

- **模拟器版本**：无需签名，可直接构建，产物为 .app（仅模拟器用）
- **真机 IPA**：需配置 Apple 证书，见下方

### 3. 下载构建产物

GitHub 仓库 → Actions → 选择运行记录 → Artifacts 下载

### 4. 生成真机可安装的 IPA（需 Apple 开发者账号）

在 GitHub 仓库 Settings → Secrets 添加：

| Secret 名称 | 说明 |
|-------------|------|
| APPLE_DEVELOPER_ID | Apple ID 邮箱 |
| APPLE_APP_SPECIFIC_PASSWORD | 应用专用密码 |
| CERTIFICATE_BASE64 | 证书 .p12 的 base64 |
| PROVISIONING_PROFILE_BASE64 | 描述文件 base64 |

然后修改 workflow 增加 Archive 和导出 IPA 步骤（需 Fastlane 或 xcodebuild archive）。

---

## 方案二：Codemagic（免费层 500 分钟/月）

项目已包含 `codemagic.yaml`，按以下步骤配置即可自动构建 IPA。

### 1. 推送配置到 GitHub

```bash
cd /opt/baoshui
git add codemagic.yaml
git commit -m 'Add Codemagic workflow'
git push
```

### 2. 在 Codemagic 添加应用

1. 注册 https://codemagic.io，用 GitHub 登录
2. 添加应用 → 选择 `alexwang-2021/baoshui` 仓库
3. 选择分支（main 或 master），点击 **Check for configuration file**

### 3. 配置 App Store Connect 集成

1. Codemagic 后台 → **Team settings** → **Integrations** → **App Store Connect**
2. 添加 API Key：
   - 在 [App Store Connect](https://appstoreconnect.apple.com) → 用户 → 密钥 → 生成 API 密钥
   - 下载 .p8 文件，记录 Issuer ID、Key ID
   - 在 Codemagic 中上传并命名为 `codemagic`（与 codemagic.yaml 中 `app_store_connect: codemagic` 一致）

### 4. 配置 iOS 代码签名

- **自动签名**：在 Codemagic 应用设置 → Code signing 中配置 Apple 账号，Codemagic 会自动创建证书和描述文件
- **手动签名**：上传已有的 .p12 证书和 .mobileprovision 描述文件

### 5. 触发构建

推送代码到 main/master 分支会自动触发，或手动点击 **Start new build**。构建完成后在 Codemagic 页面下载 IPA。

---

## 方案三：MacinCloud / MacStadium（按小时租用）

1. 租用云 Mac（约 $1/小时起）
2. 远程桌面连接
3. 安装 Xcode，按「构建iOS说明.md」本地构建

---

## 当前 workflow 说明

- 构建目标：**iOS 模拟器**（验证项目可编译）
- 产物：`App.app`（模拟器用，不能装真机）
- 真机 IPA：需在 workflow 中增加 Archive + 导出，并配置上述 Secrets

## 成本对比

| 方案 | 成本 | 真机 IPA |
|------|------|----------|
| GitHub Actions | 免费 200 分钟/月 | 需自配证书 |
| Codemagic | 免费 500 分钟/月 | 支持 |
| MacinCloud | ~$1/小时 | 支持 |
