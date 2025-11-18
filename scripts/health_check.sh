#!/bin/bash
# 健康检查脚本 - 验证 Tracking Server 是否正常运行

echo "🏥 AI Digest 服务健康检查"
echo ""

echo "1. Tracking Server (http://localhost:8000)"
if curl -s http://localhost:8000 > /dev/null 2>&1; then
    echo "   ✅ 运行正常"
else
    echo "   ❌ 无响应"
    echo "   提示：运行 ./scripts/manage_services.sh restart"
fi

echo ""
echo "日志位置: tail -20 logs/tracking-server.log"
