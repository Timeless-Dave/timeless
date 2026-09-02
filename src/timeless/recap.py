from __future__ import annotations

import json
import os
import re
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from timeless.clock import due_recap_day
from timeless.store import Store

ROOT = Path(__file__).resolve().parents[2]
PHONE_PULL = ROOT / "scripts" / "phone_aw_pull.sh"


def adb_devices() -> list[tuple[str, str]]:
    try:
        out = subprocess.check_output(["adb", "devices"], text=True, timeout=8, stderr=subprocess.DEVNULL)
    except Exception:
        return []
    rows = []
    for line in out.splitlines()[1:]:
        parts = line.split()
        if len(parts) >= 2:
            rows.append((parts[0], parts[1]))
    return rows


def connect_phone(mode: str = "wireless") -> dict[str, Any]:
    mode = mode if mode in {"wireless", "usb"} else "wireless"
    env = {**os.environ, "TIMELESS_ADB_MODE": mode}
    detail = ""
    try:
        r = subprocess.run(
            ["/bin/bash", str(PHONE_PULL)],
            check=False,
            timeout=60,
            capture_output=True,
            env=env,
        )
        detail = (r.stdout or b"").decode("utf-8", "replace") + (r.stderr or b"").decode("utf-8", "replace")
    except Exception as exc:
        return {"ok": False, "mode": mode, "detail": str(exc), "devices": []}
    devices = [serial for serial, state in adb_devices() if state == "device"]
    if mode == "usb":
        devices = [s for s in devices if ":" not in s]
    ok = bool(devices)
    return {
        "ok": ok,
        "mode": mode,
        "detail": (detail.strip() or ("phone linked" if ok else "no adb phone")),
        "devices": devices,
        "pulled": ok,
    }


def pull_phone(timeout: int = 25) -> bool:
    if not PHONE_PULL.exists():
        return False
    try:
        subprocess.run(
            ["/bin/bash", str(PHONE_PULL)],
            check=False,
            timeout=timeout,
            capture_output=True,
            env={**os.environ},
        )
        return True
    except Exception:
        return False


def _payload(event: dict[str, Any]) -> dict[str, Any]:
    raw = event.get("payload") or {}
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except Exception:
            return {}
    return raw if isinstance(raw, dict) else {}


def _humanize(text: str) -> str:
    s = (text or "").strip()
    if not s:
        return "something"
    if "://" in s:
        host = urlparse(s).netloc.replace("www.", "")
        return host or s[:48]
    parts = s.split(".")
    if len(parts) >= 3 and parts[0] in {"com", "org", "net", "io", "app"}:
        return parts[-1].replace("_", " ").replace("-", " ")
    toks = s.split()
    if len(toks) >= 2 and "." in toks[1] and toks[1].count(".") >= 2:
        return toks[0]
    return s[:56]


def _label(event: dict[str, Any]) -> str:
    payload = _payload(event)
    for key in ("app", "title", "host", "url"):
        val = payload.get(key)
        if val:
            return _humanize(str(val))
    return _humanize(str(event.get("summary") or event.get("source") or "activity"))


def _pretty_day(day: str) -> str:
    try:
        d = datetime.strptime(day, "%Y-%m-%d")
    except ValueError:
        return day
    return d.strftime("%A, %b %d").replace(" 0", " ")


def _short_weekday(day: str) -> str:
    try:
        return datetime.strptime(day, "%Y-%m-%d").strftime("%a")
    except ValueError:
        return day[:3]


def _split_goals(outcomes: str) -> list[str]:
    lines: list[str] = []
    for chunk in re.split(r"[\n;]+", outcomes or ""):
        text = re.sub(r"^\s*(?:[-•]|\d+[.)])\s*", "", chunk).strip()
        if text:
            lines.append(text)
    return lines
def _block_line(block: dict[str, Any]) -> str:
    start = str(block.get("start") or "").strip()
    end = str(block.get("end") or "").strip()
    task = str(block.get("task") or "").strip()
    if start and end:
        return f"{start}–{end}  {task}"
    return task


def day_stats(store: Store, day: str) -> dict[str, Any]:
    plan = store.get_plan(day)
    events = store.events_on_day(day)
    return {
        "day": day,
        "label": _short_weekday(day),
        "blocks": len((plan or {}).get("timeline") or []),
        "events": len(events),
        "had_plan": plan is not None,
    }


def week_compare(store: Store, day: str) -> list[dict[str, Any]]:
    start = datetime.strptime(day, "%Y-%m-%d")
    out = []
    for i in range(6, -1, -1):
        key = (start - timedelta(days=i)).strftime("%Y-%m-%d")
        out.append(day_stats(store, key))
    return out


def build_cards(store: Store, day: str, phone_synced: bool) -> list[dict[str, Any]]:
    events = store.events_on_day(day)
    plan = store.get_plan(day)
    mac = [e for e in events if e["source"] in {"url", "screen"}]
    phone = [e for e in events if e["source"] == "phone"]
    jobs = [e for e in mac if "http" in (e.get("summary") or "")]
    opps = [o for o in store.list_opportunities() if (o.get("updated_at") or o.get("created_at") or "").startswith(day)]
    counts: dict[str, int] = {}
    for e in events:
        name = _label(e)
        counts[name] = counts.get(name, 0) + 1
    ranked = sorted(counts.items(), key=lambda kv: -kv[1])[:3]
    top_lines = [f"{name} — {n} times" for name, n in ranked]
    blocks = (plan or {}).get("timeline") or []
    outcomes = ((plan or {}).get("outcomes") or "").strip()
    goal_lines = _split_goals(outcomes)
    week = week_compare(store, day)
    productivity = store.productivity_on_day(day)
    productivity_minutes = productivity.get("minutes") or {}

    cards: list[dict[str, Any]] = [
        {
            "kicker": "Recap",
            "title": _pretty_day(day),
            "stat": str(len(events)),
            "stat_label": "things logged",
            "body": "A short look at what you meant to do, and what actually showed up.",
            "lines": [],
        },
        {
            "kicker": "Plan",
            "title": "What you set out to do",
            "stat": str(len(goal_lines) or len(blocks)),
            "stat_label": "goals" if goal_lines else "time blocks",
            "body": (
                "Your goals for the day:"
                if goal_lines
                else ("You did not lock a plan for this day." if not blocks else "Time blocks you set:")
            ),
            "lines": goal_lines + [_block_line(b) for b in blocks if str(b.get("task") or "").strip()],
        },
        {
            "kicker": "Mac",
            "title": "What held the screen",
            "stat": str(len(mac)),
            "stat_label": "Mac notes",
            "body": "Most of the time was in:" if top_lines else "A quiet day on this Mac.",
            "lines": top_lines,
        },
        {
            "kicker": "Phone",
            "title": "In your hand",
            "stat": str(len(phone)),
            "stat_label": "phone notes",
            "body": (
                f"The phone checked in. It logged {len(phone)} app switches."
                if phone_synced
                else "The phone did not sync. This recap is Mac-only."
            ),
            "lines": [],
        },
        {
            "kicker": "Programs",
            "title": "Jobs and programs",
            "stat": str(len(opps) or len(jobs)),
            "stat_label": "touched",
            "body": "Roles you touched today:" if opps else "No postings were tagged today.",
            "lines": [(o.get("role") or o.get("url") or "a posting")[:56] for o in opps[:5]],
        },
        {
            "kicker": "Alignment",
            "title": "Did the day match the plan?",
            "stat": str(productivity.get("score")) if productivity.get("score") is not None else "—",
            "stat_label": "estimated productivity score",
            "body": (
                f"{productivity.get('alignment')}% of productive time matched the plan."
                if productivity.get("alignment") is not None
                else "Not enough classified activity to estimate alignment."
            ),
            "lines": [
                f"Plan-aligned — {productivity_minutes.get('aligned', 0)} min",
                f"Productive, off-plan — {productivity_minutes.get('productive_off_plan', 0)} min",
                f"Distracting — {productivity_minutes.get('distracting', 0)} min",
                f"Unknown — {productivity_minutes.get('unknown', 0)} min",
            ],
        },
        {
            "kicker": "Compare",
            "title": "Plan vs what showed up",
            "stat": str(len(events)),
            "stat_label": "today",
            "kind": "compare",
            "body": (
                f"You planned {len(blocks)} block{'s' if len(blocks) != 1 else ''}. "
                f"{len(events)} notes landed on this day."
            ),
            "lines": [],
            "compare": {
                "blocks": len(blocks),
                "events": len(events),
                "week": week,
            },
        },
    ]
    return cards


def ensure_recap(store: Store, now=None, do_pull: bool = True) -> dict[str, Any]:
    day = due_recap_day(now)
    existing = store.get_recap(day)
    if existing and existing.get("acked_at"):
        return existing
    if existing and existing.get("cards"):
        return existing
    synced = pull_phone() if do_pull else False
    cards = build_cards(store, day, synced)
    return store.save_recap(day, cards, synced)
