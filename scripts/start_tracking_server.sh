#!/bin/bash
# 启动 AI Digest 阅读行为追踪服务器

cd "$(dirname "$0")/.."

# 检查是否使用 launchd 管理
if launchctl list | grep -q "tracking-server"; then
    echo "⚠️  Tracking Server 已由 launchd 管理"
    echo "使用以下命令管理："
    echo "  查看状态: ./scripts/manage_services.sh status"
    echo "  停止服务: ./scripts/manage_services.sh stop"
    echo "  重启服务: ./scripts/manage_services.sh restart"
    exit 0
fi

echo "🚀 启动追踪服务器..."
echo ""
echo "使用方法:"
echo "  1. 服务器会在后台运行"
echo "  2. 打开 HTML 报告即可自动追踪阅读行为"
echo "  3. 使用 ./scripts/stop_tracking_server.sh 停止服务器"
echo ""
echo "💡 提示: 推荐使用 launchd 管理服务（自动重启、开机启动）"
echo "   安装: ./scripts/manage_services.sh install"
echo ""

python3 -m src.tracking.tracking_server --port 8000 &

# 保存 PID
echo $! > /tmp/ai-digest-tracking.pid

echo "✓ 追踪服务器已启动 (PID: $!)"
echo "  API 端点: http://localhost:8000/api/track"
