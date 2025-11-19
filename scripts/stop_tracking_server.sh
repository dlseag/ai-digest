#!/bin/bash
# 停止 AI Digest 阅读行为追踪服务器

PID_FILE="/tmp/ai-digest-tracking.pid"

if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if ps -p $PID > /dev/null 2>&1; then
        echo "⏹️  停止追踪服务器 (PID: $PID)..."
        kill $PID
        rm "$PID_FILE"
        echo "✓ 追踪服务器已停止"
    else
        echo "⚠️  追踪服务器未运行 (PID $PID 不存在)"
        rm "$PID_FILE"
    fi
else
    echo "⚠️  找不到 PID 文件，服务器可能未启动"
    echo "    提示：使用 'ps aux | grep tracking_server' 手动查找进程"
fi

