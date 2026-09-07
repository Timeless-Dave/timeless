#!/usr/bin/env bash
# Run the full three-run thermal protocol from docs/thermal-profile.md.
# Prereqs: plugged in, other apps closed, brain serving built frontend on :8787.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
COOLDOWN_MIN="${THERMAL_COOLDOWN_MIN:-5}"
RUN_MIN="${THERMAL_RUN_MIN:-10}"

cd "$ROOT/frontend"
echo "Building frontend…"
pnpm run build

echo "Restarting com.timeless.brain…"
launchctl kickstart -k "gui/$(id -u)/com.timeless.brain" 2>/dev/null || true
sleep 2

if ! curl -sf "http://127.0.0.1:8787/api/today" >/dev/null; then
  echo "Dashboard not reachable at http://127.0.0.1:8787/ — start the brain service first." >&2
  exit 1
fi

echo "Baseline SMC reading (may prompt for sudo)…"
"$ROOT/scripts/thermal-profile.sh" baseline 2>/dev/null || true

for mode in quiet auto full; do
  echo
  echo "========== Run: $mode (${RUN_MIN} min) =========="
  echo "Settle ${COOLDOWN_MIN} minutes if this is not the first run…"
  if [[ "$mode" != "quiet" ]]; then
    sleep "$((COOLDOWN_MIN * 60))"
  fi

  # Browser in background; powermetrics in foreground (needs sudo).
  (cd "$ROOT/frontend" && pnpm exec node scripts/thermal-browser.mjs "$mode" "$RUN_MIN") &
  BROWSER_PID=$!
  "$ROOT/scripts/thermal-profile.sh" "$mode" || true
  wait "$BROWSER_PID" 2>/dev/null || true
done

echo
echo "Done. Logs in $ROOT/docs/thermal-runs/"
