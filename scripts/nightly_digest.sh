#!/bin/bash
# Nightly AI Digest run: collects data, runs learning loop, generates report
set -euo pipefail

PROJECT_DIR="/Users/david/Documents/ai-workflow/ai-digest"
cd "$PROJECT_DIR"

# Load environment variables if present
if [ -f .env ]; then
  set -a
  source .env
  set +a
fi

# Determine runner
if command -v python3 >/dev/null 2>&1; then
  RUNNER="python3"
elif command -v python >/dev/null 2>&1; then
  RUNNER="python"
elif command -v poetry >/dev/null 2>&1; then
  RUNNER="poetry run python"
else
  echo "未找到可用的 Python 运行时" >&2
  exit 1
fi

LOG_FILE="$PROJECT_DIR/logs/nightly_digest.log"

{
  echo "==== $(date '+%Y-%m-%d %H:%M:%S') Nightly digest run ===="
  $RUNNER src/main.py --days-back 3
  echo "==== Completed at $(date '+%Y-%m-%d %H:%M:%S') ===="
} >>"$LOG_FILE" 2>&1
