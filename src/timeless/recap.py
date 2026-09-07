from __future__ import annotations

import os
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

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


def day_stats(store: Store, day: str) -> dict[str, Any]:
    """Goals set against goals finished — like units, unlike the old blocks/events pair."""
    plan = store.get_plan(day)
    progress = (plan or {}).get("goal_progress") or {}
    return {
        "day": day,
        "label": _short_weekday(day),
        "goals": progress.get("counted") or 0,
        "done": progress.get("done") or 0,
        "partial": progress.get("partial") or 0,
        "had_plan": plan is not None,
    }


def week_compare(store: Store, day: str) -> list[dict[str, Any]]:
    start = datetime.strptime(day, "%Y-%m-%d")
    out = []
    for i in range(6, -1, -1):
        key = (start - timedelta(days=i)).strftime("%Y-%m-%d")
        out.append(day_stats(store, key))
    return out


def _goal_line(goal: dict[str, Any]) -> str:
    """One goal as it reads in a static card, with its own words attached."""
    label = GOAL_LABELS.get(goal.get("status") or "planned", "Planned")
    line = f"{goal.get('text') or 'a goal'} — {label.lower()}"
    if goal.get("note"):
        line += f" ({goal['note']})"
    carried = goal.get("deferred_count") or 0
    if carried:
        line += f" · carried over {carried}x"
    return line


GOAL_LABELS = {
    "planned": "Not judged yet",
    "active": "Still open",
    "done": "Done",
    "partial": "Partly done",
    "deferred": "Deferred",
    "dropped": "Dropped",
}


def build_cards(store: Store, day: str, phone_synced: bool) -> list[dict[str, Any]]:
    """The end of the daily loop: review each goal, correct the evidence, keep a
    lesson, and see what carries into tomorrow.

    Interactive cards carry a `kind` and the `day` they act on; the recap screen
    reads live goal and evidence state for those rather than this snapshot, so a
    status changed mid-recap is never stale.
    """
    events = store.events_on_day(day)
    plan = store.get_plan(day)
    phone = [e for e in events if e["source"] == "phone"]
    opps = [o for o in store.list_opportunities() if (o.get("updated_at") or o.get("created_at") or "").startswith(day)]
    goals = (plan or {}).get("goals") or []
    progress = (plan or {}).get("goal_progress") or {}
    unjudged = [g for g in goals if (g.get("status") or "planned") in {"planned", "active"}]
    open_goals = [g for g in goals if (g.get("status") or "planned") in {"planned", "active", "partial", "deferred"}]
    week = week_compare(store, day)
    productivity = store.productivity_on_day(day)
    minutes = productivity.get("minutes") or {}
    reflection = store.get_reflection(day)
    counted = progress.get("counted") or 0
    done = progress.get("done") or 0

    cards: list[dict[str, Any]] = [
        {
            "kicker": "Recap",
            "title": _pretty_day(day),
            "stat": f"{done}/{counted}" if counted else "—",
            "stat_label": "goals finished",
            "body": (
                "Close the day: judge each goal, correct anything the Mac read wrong, and keep one lesson."
                if goals
                else "You did not plan this day, so there is nothing to judge. A short look at what showed up."
            ),
            "lines": [],
        },
        {
            "kicker": "Goals",
            "title": "What did you actually finish?",
            "stat": str(len(unjudged)) if unjudged else str(counted),
            "stat_label": "still to judge" if unjudged else "goals set",
            "kind": "goals",
            "day": day,
            "body": (
                "Only you can say whether these are done. Work away from this Mac counts."
                if goals
                else "No goals were set for this day."
            ),
            "lines": [_goal_line(g) for g in goals],
        },
        {
            "kicker": "Evidence",
            "title": "What the Mac saw",
            "stat": str(productivity.get("score")) if productivity.get("score") is not None else "—",
            "stat_label": "estimated alignment",
            "kind": "evidence",
            "day": day,
            "body": (
                f"{productivity.get('tracked_minutes', 0)} min observed, "
                f"{productivity.get('judged_minutes', 0)} min judged, "
                f"{minutes.get('unknown', 0)} min unclassified. "
                + (
                    "The phone checked in too."
                    if phone_synced
                    else "The phone did not sync, so this is Mac-only."
                )
            ),
            "lines": [
                f"On plan — {minutes.get('aligned', 0)} min",
                f"Useful detour — {minutes.get('productive_off_plan', 0)} min",
                f"Distraction — {minutes.get('distracting', 0)} min",
                f"Unclassified — {minutes.get('unknown', 0)} min",
            ],
        },
        {
            "kicker": "Programs",
            "title": "Jobs and programs",
            "stat": str(len(opps)),
            "stat_label": "touched",
            "body": "Roles you touched today:" if opps else "No postings were tagged today.",
            "lines": [(o.get("role") or o.get("url") or "a posting")[:56] for o in opps[:5]],
        },
        {
            "kicker": "Compare",
            "title": "Goals set against goals finished",
            "stat": f"{done}/{counted}" if counted else "—",
            "stat_label": "today",
            "kind": "compare",
            "day": day,
            "body": (
                f"You set {counted} goal{'s' if counted != 1 else ''} and finished {done}."
                if counted
                else "No goals were set for this day."
            ),
            "lines": [],
            "compare": {"goals": counted, "done": done, "week": week},
        },
        {
            "kicker": "Lesson",
            "title": "One thing worth remembering",
            "stat": "1",
            "stat_label": "line is enough",
            "kind": "lesson",
            "day": day,
            "body": "What would you tell yourself before starting this day again?",
            "lines": [],
            "lesson": reflection.get("lesson"),
        },
        {
            "kicker": "Tomorrow",
            "title": "What comes with you",
            "stat": str(len(open_goals)),
            "stat_label": "goals still open",
            "kind": "tomorrow",
            "day": day,
            "body": (
                "These are offered when you plan your next day. Drop anything that no longer matters."
                if open_goals
                else "Nothing is left open. Tomorrow starts clean."
            ),
            "lines": [_goal_line(g) for g in open_goals],
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
