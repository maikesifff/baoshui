# 自报税 - 项目结构

## 前后端分离

### 前端（静态页面）
| 文件 | 说明 |
|------|------|
| `index.html` | 首页（待办、记账入口） |
| `report.html` | 报表页（财务报表） |
| `download.html` | 下载页 |
| `styles.css` | 全局样式 |
| `report.css` | 报表页样式 |
| `app.js` | 首页逻辑 |
| `report.js` | 报表页逻辑 |
| `config.js` | API 配置 |

### 后端（API）
| 文件 | 说明 |
|------|------|
| `server.py` | Flask 服务，提供 API 和静态文件 |

### API 端点
- `POST /api/sms/send` - 发送验证码
- `POST /api/auth/login` - 登录
- `POST /api/auth/register` - 注册
- `POST /api/user/company-name` - 保存公司名称
- `GET /api/report/summary` - 报表概览数据

## 页面导航
- 首页 → 财务报表 → `report.html`
- 报表页 ← 返回 → 首页

## 构建 App
```bash
npm run build          # 复制前端文件到 www/
npm run cap:sync       # 同步到 Capacitor 原生工程
```
