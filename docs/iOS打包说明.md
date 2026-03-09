# 自报税 iOS 打包说明

## 环境要求

- **必须使用 macOS**（苹果包只能在 Mac 上打）
- 安装 **Xcode**（App Store 或开发者官网下载）
- 如需真机/上架：Apple Developer 账号（付费）

## 一、在 Mac 上打包

### 1. 同步项目（若在 Linux 已跑过可跳过）

在项目根目录执行：

```bash
cd /path/to/baoshui
npm run cap:sync:ios
```

### 2. 用 Xcode 打开 iOS 工程

```bash
npx cap open ios
```

或手动打开：`ios/App/App.xcodeproj`

### 3. 在 Xcode 中

- **签名**：选中项目 → Signing & Capabilities → 选择你的 Team（需 Apple ID 登录）
- **模拟器包**：顶部选任意模拟器（如 iPhone 15）→ 菜单 **Product → Build**，生成的是模拟器用 app
- **真机/归档包**：顶部选 “Any iOS Device” → **Product → Archive**，归档后可导出 IPA（需付费开发者账号）

### 4. 命令行打包（可选）

在 **Mac** 上、已安装 Xcode 时：

```bash
cd ios/App
xcodebuild -scheme App -configuration Release -sdk iphonesimulator -derivedDataPath build
# 模拟器 app 在 build/Build/Products/Release-iphonesimulator/ 下
```

真机 IPA 一般需在 Xcode 里用 Archive → Distribute App 导出。

## 二、当前已就绪内容

- `npm run cap:sync:ios` 已执行，`www` 和配置已同步到 `ios/App/App/public`
- 应用名：**自报税**
- 远程地址：`https://me.gaoxin.xin/baoshui/`（Capacitor 内已配置）

把本仓库拷到 Mac 后，按上述步骤即可打苹果包。
