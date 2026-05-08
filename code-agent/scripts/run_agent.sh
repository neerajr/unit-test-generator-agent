#!/usr/bin/env bash
# run_agent.sh — Cron entry point for the weekly code analysis run.
# Cron expression is read from config/config.yaml (schedule.cron_expression).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Derive OUTPUT_BASE from config.yaml (falls back to ~/agent-output on any error)
OUTPUT_BASE=$(python3 -c "
import yaml, pathlib, sys
try:
    raw = yaml.safe_load(open('$PROJECT_DIR/config/config.yaml'))
    base = raw.get('output', {}).get('base_dir', '~/agent-output')
    print(pathlib.Path(base).expanduser())
except Exception:
    print(pathlib.Path('~/agent-output').expanduser())
" 2>/dev/null || echo "$HOME/agent-output")

LOG_FILE="$OUTPUT_BASE/reports/run.log"

mkdir -p "$OUTPUT_BASE/reports"

echo "=======================================" >> "$LOG_FILE"
echo "code-agent run started: $(date -Iseconds)" >> "$LOG_FILE"
echo "=======================================" >> "$LOG_FILE"

cd "$PROJECT_DIR"

if [[ ! -d venv ]]; then
    echo "[ERROR] venv not found at $PROJECT_DIR/venv. Run setup.sh first." >> "$LOG_FILE"
    exit 1
fi

# shellcheck source=/dev/null
source venv/bin/activate

python3 agent/main.py >> "$LOG_FILE" 2>&1

echo "code-agent run finished: $(date -Iseconds)" >> "$LOG_FILE"
