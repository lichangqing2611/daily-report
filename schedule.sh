#!/bin/bash
# Daily AI News Report - Launcher for cron/launchd
# Usage: ./schedule.sh

set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

# Load environment variables if .env exists
if [ -f ".env" ]; then
    export $(grep -v '^#' .env | xargs)
fi

# Log output
LOG_DIR="$PROJECT_DIR/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/cron-$(date +%Y-%m-%d).log"

echo "[$(date)] Starting daily report..." >> "$LOG_FILE"
/usr/bin/python3 run.py >> "$LOG_FILE" 2>&1
EXIT_CODE=$?
echo "[$(date)] Finished with exit code $EXIT_CODE" >> "$LOG_FILE"

exit $EXIT_CODE
