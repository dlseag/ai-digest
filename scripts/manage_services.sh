#!/bin/bash
# AI Digest Services Manager - 统一管理 tracking server

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
LAUNCHD_DIR="$PROJECT_ROOT/launchd"
LOGS_DIR="$PROJECT_ROOT/logs"

TRACKING_PLIST="com.aiworkflow.tracking-server.plist"
LEGACY_WORKER_PLIST="com.aiworkflow.deep-dive-worker.plist"

# 创建日志目录
mkdir -p "$LOGS_DIR"

# 从 .env 文件加载环境变量
if [ -f "$PROJECT_ROOT/.env" ]; then
    export $(grep -v '^#' "$PROJECT_ROOT/.env" | xargs)
fi

# 检测 Python 路径
PYTHON_PATH=$(which python3)

# 替换 plist 中的路径占位符
prepare_plist() {
    local plist_file="$1"
    local temp_file="/tmp/$(basename $plist_file)"
    
    sed "s|/usr/local/bin/python3|$PYTHON_PATH|g" "$LAUNCHD_DIR/$plist_file" > "$temp_file"
    sed -i '' "s|\${POE_API_KEY}|$POE_API_KEY|g" "$temp_file"
    
    echo "$temp_file"
}

cleanup_legacy_worker() {
    local legacy_agent="$HOME/Library/LaunchAgents/$LEGACY_WORKER_PLIST"
    if [ -f "$legacy_agent" ]; then
        echo "⚠️  检测到已废弃的 deep-dive worker，正在自动卸载..."
        launchctl unload "$legacy_agent" 2>/dev/null
        rm -f "$legacy_agent"
        echo "✓ 已卸载 legacy deep-dive worker（该服务在即时深度研究中不再需要）"
    fi
}

cleanup_legacy_worker

case "$1" in
    start)
        echo "🚀 启动 AI Digest 服务..."
        TRACKING_TEMP=$(prepare_plist "$TRACKING_PLIST")
        launchctl load "$TRACKING_TEMP"
        echo "✓ Tracking Server 已启动"
        echo "查看状态: ./scripts/manage_services.sh status"
        ;;
    stop)
        echo "🛑 停止 AI Digest 服务..."
        launchctl unload ~/Library/LaunchAgents/$TRACKING_PLIST 2>/dev/null
        echo "✓ 服务已停止"
        ;;
    restart)
        echo "🔄 重启 AI Digest 服务..."
        $0 stop
        sleep 2
        $0 start
        ;;
    status)
        echo "📊 AI Digest 服务状态："
        echo ""
        echo "Tracking Server:"
        launchctl list | grep tracking-server || echo "  未运行"
        echo ""
        echo "最近日志："
        echo "  Tracking: tail -20 $LOGS_DIR/tracking-server.log"
        ;;
    logs)
        echo "📋 查看实时日志 (Ctrl+C 退出)："
        tail -f "$LOGS_DIR/tracking-server.log"
        ;;
    install)
        echo "📦 安装 Tracking Server 到 launchd..."
        TRACKING_TEMP=$(prepare_plist "$TRACKING_PLIST")
        cp "$TRACKING_TEMP" ~/Library/LaunchAgents/$TRACKING_PLIST
        echo "✓ 服务已安装到 ~/Library/LaunchAgents/"
        echo "下次启动：./scripts/manage_services.sh start"
        ;;
    uninstall)
        echo "🗑️  卸载 Tracking Server 服务..."
        $0 stop
        rm -f ~/Library/LaunchAgents/$TRACKING_PLIST
        echo "✓ 服务已卸载"
        ;;
    *)
        echo "AI Digest Services Manager"
        echo ""
        echo "用法: $0 {install|start|stop|restart|status|logs|uninstall}"
        echo ""
        echo "命令说明："
        echo "  install   - 安装 Tracking Server 到 launchd（首次使用）"
        echo "  start     - 启动 Tracking Server"
        echo "  stop      - 停止 Tracking Server"
        echo "  restart   - 重启 Tracking Server"
        echo "  status    - 查看服务状态"
        echo "  logs      - 查看实时日志"
        echo "  uninstall - 卸载服务"
        exit 1
        ;;
esac
