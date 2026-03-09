#!/bin/bash
# 在部署 baoshui 的服务器上运行，用于排查 POST /api/user/companies/delete 返回 405
# 用法: bash scripts/check-delete-405.sh

echo "=== 1. 看当前是谁在监听 8083（或 baoshui 用的端口）==="
sudo lsof -i :8083 2>/dev/null || true

echo ""
echo "=== 2. 看 baoshui 进程和启动参数 ==="
ps aux | grep -E 'baoshui|gunicorn.*server' | grep -v grep

echo ""
echo "=== 3. 若用 Nginx 反向代理，看 /baoshui 的 location 是否限制了 POST ==="
sudo nginx -T 2>/dev/null | grep -A 20 'location.*baoshui' || echo "（无 nginx 或无法读取配置）"

echo ""
echo "=== 4. 本地直连 Flask 测 POST（在项目目录执行）==="
echo "可先: curl -s -o /dev/null -w '%{http_code}' -X POST http://127.0.0.1:8083/api/user/companies/delete -H 'Content-Type: application/json' -d '{}'"
echo "预期: 400（缺 company_id）或 401（缺 token），不应该是 405"

echo ""
echo "=== 5. 触发删除时看应用日志是否收到请求 ==="
echo "在另一终端执行: sudo journalctl -u baoshui -f --no-pager"
echo "或: tail -f /var/log/gunicorn/baoshui.log（视实际日志路径而定）"
echo "然后浏览器再点一次删除，看是否出现 [companies/delete] POST received"
