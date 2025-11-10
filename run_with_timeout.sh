#!/bin/bash
# AI简报生成脚本（带超时保护）
# 用法: ./run_with_timeout.sh [超时秒数，默认300] [其他参数]

TIMEOUT=${1:-300}  # 默认5分钟超时
shift

cd "$(dirname "$0")"

echo "========================================"
echo "AI简报生成 (超时: ${TIMEOUT}秒)"
echo "========================================"

# 设置环境变量，禁用模型下载，并使用项目本地缓存目录
export TRANSFORMERS_OFFLINE=1
export HF_HUB_OFFLINE=1
export HF_HOME="$(pwd)/.hf_cache"
export TRANSFORMERS_CACHE="$(pwd)/.hf_cache/transformers"
mkdir -p "$HF_HOME" "$TRANSFORMERS_CACHE"

# 使用 Perl 实现超时（macOS兼容）
perl -e "alarm $TIMEOUT; exec @ARGV" python src/main.py "$@" 2>&1

EXIT_CODE=$?

if [ $EXIT_CODE -eq 142 ] || [ $EXIT_CODE -eq 124 ]; then
    echo ""
    echo "========================================"
    echo "❌ 运行超时 (${TIMEOUT}秒)"
    echo "========================================"
    exit 1
elif [ $EXIT_CODE -ne 0 ]; then
    echo ""
    echo "========================================"
    echo "❌ 运行失败 (退出码: $EXIT_CODE)"
    echo "========================================"
    exit $EXIT_CODE
else
    echo ""
    echo "========================================"
    echo "✓ 运行成功"
    echo "========================================"
fi
