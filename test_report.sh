#!/bin/bash
# 简报质量测试快速运行脚本

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "=================================="
echo "🧪 简报质量测试"
echo "=================================="

# 查找最新的简报文件
LATEST_HTML=$(ls -t output/weekly_report_*.html 2>/dev/null | head -1)
LATEST_JSON=$(ls -t output/collected_items_*.json 2>/dev/null | head -1)

if [ -z "$LATEST_HTML" ]; then
    echo -e "${RED}❌ 未找到简报文件${NC}"
    echo "请先运行: python -m src.main"
    exit 1
fi

echo "测试文件: $LATEST_HTML"
if [ -n "$LATEST_JSON" ]; then
    echo "原始数据: $LATEST_JSON"
fi
echo ""

# 运行测试
if [ -n "$LATEST_JSON" ]; then
    python tests/test_report_quality.py --html "$LATEST_HTML" --json "$LATEST_JSON"
else
    python tests/test_report_quality.py --html "$LATEST_HTML"
fi

TEST_RESULT=$?

echo ""
if [ $TEST_RESULT -eq 0 ]; then
    echo -e "${GREEN}✅ 所有测试通过！${NC}"
else
    echo -e "${YELLOW}⚠️  发现问题，请查看上面的详细信息${NC}"
fi

exit $TEST_RESULT

