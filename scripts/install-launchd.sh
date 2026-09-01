#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
HOME_DIR="$HOME"
SUPPORT="$HOME/Library/Application Support/Timeless"
VENV="$SUPPORT/venv"
DEST="$HOME/Library/LaunchAgents"
LOG="$SUPPORT/logs"
mkdir -p "$DEST" "$LOG" "$SUPPORT/bin" "$ROOT/dist"

if [ ! -x "$VENV/bin/timeless" ]; then
  python3 -m venv "$VENV"
  "$VENV/bin/pip" install -e "$ROOT" -q
fi

if [ -f "$ROOT/frontend/package.json" ]; then
  echo "Building frontend SPA…"
  (cd "$ROOT/frontend" && npm ci && npm run build)
fi

if [ ! -x "$ROOT/dist/TimelessOverlay" ]; then
  swiftc -O -o "$ROOT/dist/TimelessOverlay" "$ROOT/macos/TimelessOverlay.swift" -framework Cocoa -framework WebKit
fi
cp "$ROOT/dist/TimelessOverlay" "$SUPPORT/bin/TimelessOverlay"
chmod +x "$SUPPORT/bin/TimelessOverlay"
if [ ! -x "$ROOT/dist/TimelessCal" ]; then
  swiftc -O -o "$ROOT/dist/TimelessCal" "$ROOT/macos/TimelessCal.swift" -framework EventKit -framework Foundation
fi
cp "$ROOT/dist/TimelessCal" "$SUPPORT/bin/TimelessCal"
chmod +x "$SUPPORT/bin/TimelessCal"

render() {
  local src="$1" dst="$2"
  sed -e "s|VENV|$VENV|g" -e "s|SUPPORT|$SUPPORT|g" -e "s|ROOT|$ROOT|g" -e "s|HOME|$HOME_DIR|g" "$src" > "$dst"
}

render "$ROOT/macos/launchd/com.timeless.brain.plist.tmpl" "$DEST/com.timeless.brain.plist"
render "$ROOT/macos/launchd/com.timeless.overlay.plist.tmpl" "$DEST/com.timeless.overlay.plist"
render "$ROOT/macos/launchd/com.timeless.aw-ingest.plist.tmpl" "$DEST/com.timeless.aw-ingest.plist"
render "$ROOT/macos/launchd/com.timeless.screenpipe.plist.tmpl" "$DEST/com.timeless.screenpipe.plist"
render "$ROOT/macos/launchd/com.timeless.sp-ingest.plist.tmpl" "$DEST/com.timeless.sp-ingest.plist"
render "$ROOT/macos/launchd/com.timeless.phone-aw.plist.tmpl" "$DEST/com.timeless.phone-aw.plist"
render "$ROOT/macos/launchd/com.timeless.cal-ingest.plist.tmpl" "$DEST/com.timeless.cal-ingest.plist"
render "$ROOT/macos/launchd/com.timeless.mail-ingest.plist.tmpl" "$DEST/com.timeless.mail-ingest.plist"
render "$ROOT/macos/launchd/com.timeless.halt-escalate.plist.tmpl" "$DEST/com.timeless.halt-escalate.plist"

for label in com.timeless.brain com.timeless.overlay com.timeless.aw-ingest com.timeless.screenpipe com.timeless.sp-ingest com.timeless.phone-aw com.timeless.cal-ingest com.timeless.mail-ingest com.timeless.halt-escalate; do
  launchctl bootout "gui/$(id -u)/$label" 2>/dev/null || true
done
pkill -f TimelessOverlay 2>/dev/null || true
pkill -f '/Timeless/venv/bin/timeless' 2>/dev/null || true
sleep 1

for label in com.timeless.brain com.timeless.overlay com.timeless.aw-ingest com.timeless.screenpipe com.timeless.sp-ingest com.timeless.phone-aw com.timeless.cal-ingest com.timeless.mail-ingest com.timeless.halt-escalate; do
  launchctl bootstrap "gui/$(id -u)" "$DEST/${label}.plist"
  launchctl enable "gui/$(id -u)/$label"
  launchctl kickstart -k "gui/$(id -u)/$label"
done

osascript -e 'tell application "System Events" to make login item at end with properties {path:"/Applications/ActivityWatch.app", hidden:false}' >/dev/null 2>&1 || true

echo "LaunchAgents installed. Brain: http://127.0.0.1:8787"
