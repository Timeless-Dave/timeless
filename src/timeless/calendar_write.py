from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

BIN = Path.home() / "Library/Application Support/Timeless/bin/TimelessCal"


def create_calendar_event(
    title: str,
    start_at: str,
    end_at: str,
    join_url: str | None = None,
    notes: str | None = None,
) -> dict[str, Any]:
    payload = json.dumps(
        {
            "title": title,
            "start_at": start_at,
            "end_at": end_at,
            "join_url": join_url or "",
            "notes": notes or "",
        }
    )
    if os.environ.get("TIMELESS_SKIP_CAL"):
        return {"ok": False, "error": "calendar write skipped"}
    if not BIN.exists():
        return {"ok": False, "error": "TimelessCal missing; run scripts/build-cal.sh"}
    try:
        out = subprocess.check_output(
            [str(BIN), "create"],
            input=payload.encode(),
            timeout=15,
            stderr=subprocess.STDOUT,
        )
        uid = out.decode("utf-8", "replace").strip().splitlines()[-1]
        return {"ok": True, "uid": uid}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def sync_calendar_events(events: list[dict[str, Any]]) -> dict[str, Any]:
    if os.environ.get("TIMELESS_SKIP_CAL"):
        return {"ok": False, "error": "calendar write skipped"}
    if not BIN.exists():
        return {"ok": False, "error": "TimelessCal missing; run scripts/build-cal.sh"}
    try:
        out = subprocess.check_output(
            [str(BIN), "sync"],
            input=json.dumps({"events": events}).encode(),
            timeout=45,
            stderr=subprocess.STDOUT,
        )
        result = json.loads(out.decode("utf-8", "replace").strip().splitlines()[-1])
        return {"ok": True, **result}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
