# iOS OTA 安装 - HTTPS 配置说明

## 已配置

### 1. Nginx（me.gaoxin.xin）

已在 `me.gaoxin.xin` 下添加 `/baoshui/` 反向代理到 8083 端口，并设置 `X-Forwarded-Prefix`。

### 2. 访问地址（HTTPS）

| 功能 | 地址 |
|------|------|
| 首页 | https://me.gaoxin.xin/baoshui/ |
| 下载页 | https://me.gaoxin.xin/baoshui/download |
| 上传 IPA | https://me.gaoxin.xin/baoshui/ios-upload |
| OTA 安装页 | https://me.gaoxin.xin/baoshui/download/ios-install |

### 3. 生效步骤

1. **重载 Nginx**：
   ```bash
   nginx -t && nginx -s reload
   ```

2. **确保 baoshui 服务运行**：
   ```bash
   cd /opt/baoshui && python3 server.py &
   ```

3. **上传 IPA**：访问 https://me.gaoxin.xin/baoshui/ios-upload 上传 App.ipa

4. **iPhone 安装**：在 iPhone Safari 中打开 https://me.gaoxin.xin/baoshui/download/ios-install，点击「安装 App」

### 4. 可选：自定义域名

若使用其他 HTTPS 域名，可设置环境变量：

```bash
export BAOSHUI_OTA_BASE_URL=https://你的域名.com/baoshui
```

然后重启 baoshui 服务。
