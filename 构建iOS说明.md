# 自报税 - iOS 构建说明

## 重要说明

**iOS 应用必须在 macOS 上使用 Xcode 构建**，当前 Linux 服务器无法生成 IPA 安装包。

**无 Mac 可选**：使用云 Mac（GitHub Actions、Codemagic 等），详见「云Mac构建说明.md」。

## 环境要求

- **macOS**（需 Apple 电脑）
- **Xcode**（从 App Store 安装）
- **Apple Developer 账号**（真机安装或上架 App Store 需付费开发者账号）

## 构建步骤

### 1. 将项目拷贝到 Mac

将整个 `/opt/baoshui` 目录（或 `baoshui-android-source.zip` 解压后）拷贝到 Mac。

### 2. 安装依赖

```bash
cd baoshui
npm install
```

### 3. 同步 iOS 项目

```bash
npm run build
npm run cap:sync:ios
```

### 4. 在 Xcode 中打开并构建

```bash
npm run cap:open:ios
```

或手动打开：`ios/App/App.xcworkspace`（注意是 .xcworkspace，不是 .xcodeproj）

### 5. 在 Xcode 中

1. 选择开发团队（Signing & Capabilities）
2. 连接真机或选择模拟器
3. **Product → Build** 编译
4. **Product → Archive** 打包（需连接真机或选择 Generic iOS Device）
5. 导出 IPA：Window → Organizer → Distribute App

## 输出位置

- 模拟器运行：直接在 Xcode 中 Run
- 真机/IPA：Archive 后在 Organizer 中导出

## 已配置

- `Info.plist` 已添加 `NSAppTransportSecurity` 允许 HTTP（对接本地后端）
- API 地址在 `config.js` 中配置
