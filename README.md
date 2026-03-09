# 自报税 - 手机端

自报税应用的手机端页面，支持注册/登录功能，可打包为 Android APK。

## 功能

- 主页介绍（自报税、套餐价格、使用说明）
- 注册/登录弹窗（手机号 + 验证码，支持线上登录）
- 下载 APP（Web 下载页）
- 底部导航栏（主页、聊天、记账、发现、我的）

## 使用方式

### 浏览器预览

```bash
# 方式一：带登录 API 的后端（推荐）
pip install flask
python3 server.py
# 访问 http://localhost:8083
# 下载页: http://localhost:8083/download

# 方式二：仅静态文件
python3 -m http.server 8083
```

### 打包 Android APK

1. **配置 API 地址**：编辑 `config.js`，设置 `BASE_URL`
   - 模拟器：`http://10.0.2.2:端口`
   - 真机（同局域网）：`http://电脑IP:端口`

2. **环境要求**：Node.js 18+、Android Studio、配置 `ANDROID_HOME`

3. **构建**：
   ```bash
   npm run build          # 复制资源到 www
   npm run cap:sync       # 同步到 Android
   npm run cap:open       # 打开 Android Studio
   ```
   在 Android Studio 中：Build → Build Bundle(s) / APK(s) → Build APK(s)

4. **APK 输出**：`android/app/build/outputs/apk/debug/app-debug.apk`

## 后端 API 约定

| 接口 | 方法 | 请求体 | 说明 |
|------|------|--------|------|
| /api/sms/send | POST | `{ phone: "13800138000" }` | 发送验证码 |
| /api/auth/login | POST | `{ phone, code }` | 登录/注册，返回 `{ token }` 或 `{ data: { token } }` |

## 文件结构

```
baoshui/
├── index.html
├── styles.css
├── app.js
├── config.js       # API 地址配置
├── www/            # Capacitor 静态资源
├── android/        # Android 原生项目
├── ios/            # iOS 原生项目（需 Mac + Xcode 构建）
├── capacitor.config.json
└── package.json
```
