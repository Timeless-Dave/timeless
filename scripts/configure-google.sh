#!/bin/bash
set -euo pipefail

SUPPORT_DIR="$HOME/Library/Application Support/Timeless"
CLIENT_FILE="$SUPPORT_DIR/google-client.json"

read -r -p "Google OAuth client ID: " CLIENT_ID
read -r -s -p "Google OAuth client secret: " CLIENT_SECRET
echo

if [[ -z "$CLIENT_ID" || -z "$CLIENT_SECRET" ]]; then
  echo "Client ID and secret are required." >&2
  exit 1
fi

mkdir -p "$SUPPORT_DIR"
umask 077
CLIENT_ID="$CLIENT_ID" CLIENT_SECRET="$CLIENT_SECRET" CLIENT_FILE="$CLIENT_FILE" python3 -c '
import json, os, pathlib
path = pathlib.Path(os.environ["CLIENT_FILE"])
path.write_text(json.dumps({
    "client_id": os.environ["CLIENT_ID"],
    "client_secret": os.environ["CLIENT_SECRET"],
    "redirect_uri": "http://127.0.0.1:8787/oauth/google/callback",
}), encoding="utf-8")
'
chmod 600 "$CLIENT_FILE"

launchctl kickstart -k "gui/$(id -u)/com.timeless.brain" 2>/dev/null || true
echo "Google Sheets configured. Open http://127.0.0.1:8787 and connect from Programs."
