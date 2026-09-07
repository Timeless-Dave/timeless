#!/usr/bin/env bash
# Run one 10-minute thermal sample for a Timeless effects mode.
# Usage: ./scripts/thermal-profile.sh quiet|auto|full
# Requires: plugged-in Mac, dashboard open in Chrome, other apps closed.
set -euo pipefail

MODE="${1:-}"
if [[ "$MODE" != "quiet" && "$MODE" != "auto" && "$MODE" != "full" && "$MODE" != "baseline" ]]; then
  echo "Usage: $0 quiet|auto|full|baseline" >&2
  exit 1
fi

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT_DIR="$ROOT/docs/thermal-runs"
STAMP="$(date -u +%Y-%m-%dT%H-%M-%SZ)"
OUT_FILE="$OUT_DIR/${STAMP}__${MODE}.log"

mkdir -p "$OUT_DIR"

{
  echo "=== Timeless thermal run ==="
  echo "mode: $MODE"
  echo "started: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "dashboard: http://127.0.0.1:8787/"
  echo "instructions: set Theme → Visual effects → $MODE in the dashboard, then leave the tab foreground."
  echo
} | tee "$OUT_FILE"

if ! command -v powermetrics >/dev/null 2>&1; then
  echo "powermetrics not found (macOS only)." | tee -a "$OUT_FILE"
  exit 1
fi

if [[ "$MODE" == "baseline" ]]; then
  echo "Baseline SMC reading (0 min)…" | tee -a "$OUT_FILE"
  sudo powermetrics --samplers smc -i1 -n1 2>&1 | tee -a "$OUT_FILE" | grep -E 'Fan|die temperature' || true
  exit 0
fi

echo "Sampling fan RPM and CPU die temperature every 60s for 11 minutes (0–10 min)…" | tee -a "$OUT_FILE"
echo "You may be prompted for sudo." | tee -a "$OUT_FILE"

sudo powermetrics --samplers smc -i 60000 -n 11 2>&1 | tee -a "$OUT_FILE" | grep -E 'Fan|die temperature' || true

{
  echo
  echo "finished: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "log: $OUT_FILE"
} | tee -a "$OUT_FILE"
