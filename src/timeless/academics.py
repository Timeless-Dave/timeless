from __future__ import annotations

import json
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any

from timeless.clock import zone


ROOT = Path(__file__).resolve().parents[2]
ACADEMICS = ROOT / "config" / "academics"
WEEKDAYS = {"MO": 0, "TU": 1, "WE": 2, "TH": 3, "FR": 4, "SA": 5, "SU": 6}
STANDARD_PRESETS = ["Code", "LeetCode", "Coursera", "Algorithms", "Applications", "Reading", "Writing", "Review notes"]


def semesters() -> list[dict[str, Any]]:
    out = []
    for path in sorted(ACADEMICS.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(data, dict) and data.get("id"):
            out.append(data)
    return out


def current_semester(on_day: str | None = None) -> dict[str, Any] | None:
    target = on_day or datetime.now(zone()).strftime("%Y-%m-%d")
    active = [s for s in semesters() if s.get("starts_on", "") <= target <= s.get("term_ends_on", "")]
    if active:
        return active[-1]
    future = [s for s in semesters() if s.get("starts_on", "") > target]
    return future[0] if future else (semesters()[-1] if semesters() else None)


def semester_public(semester: dict[str, Any]) -> dict[str, Any]:
    courses = semester.get("courses") or []
    return {
        "id": semester["id"],
        "name": semester.get("name"),
        "starts_on": semester.get("starts_on"),
        "instruction_ends_on": semester.get("instruction_ends_on"),
        "term_ends_on": semester.get("term_ends_on"),
        "source": semester.get("source"),
        "courses": courses,
        "academic_dates": semester.get("academic_dates") or [],
        "presets": STANDARD_PRESETS + [course.get("preset") or course.get("title") for course in courses],
    }


def _iso(local_dt: datetime) -> str:
    return local_dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def semester_events(semester: dict[str, Any]) -> list[dict[str, Any]]:
    tz = zone()
    starts = date.fromisoformat(semester["starts_on"])
    instruction_ends = date.fromisoformat(semester["instruction_ends_on"])
    excluded = {date.fromisoformat(value) for value in semester.get("no_class_dates") or []}
    events = []
    cursor = starts
    while cursor <= instruction_ends:
        if cursor not in excluded:
            for course in semester.get("courses") or []:
                if cursor.weekday() not in {WEEKDAYS[d] for d in course.get("days") or [] if d in WEEKDAYS}:
                    continue
                start_t = time.fromisoformat(course["start"])
                end_t = time.fromisoformat(course["end"])
                events.append({
                    "uid": f"{semester['id']}:course:{course['code']}:{cursor.isoformat()}",
                    "title": f"{course['code']} · {course['title']}",
                    "start_at": _iso(datetime.combine(cursor, start_t, tzinfo=tz)),
                    "end_at": _iso(datetime.combine(cursor, end_t, tzinfo=tz)),
                    "location": course.get("location") or "",
                    "notes": f"Timeless kind: course\n{semester.get('name')} · imported by Timeless",
                    "all_day": False,
                })
        cursor += timedelta(days=1)
    for item in semester.get("academic_dates") or []:
        start_day = date.fromisoformat(item.get("start_date") or item["date"])
        end_day = date.fromisoformat(item.get("end_date") or item.get("date") or item["start_date"])
        events.append({
            "uid": f"{semester['id']}:academic:{start_day.isoformat()}:{item['title']}",
            "title": f"UAPB · {item['title']}",
            "start_at": _iso(datetime.combine(start_day, time.min, tzinfo=tz)),
            "end_at": _iso(datetime.combine(end_day + timedelta(days=1), time.min, tzinfo=tz)),
            "location": "University of Arkansas at Pine Bluff",
            "notes": f"Timeless kind: {'deadline' if item.get('kind') == 'deadline' else 'calendar_note'}\n{semester.get('source')} · imported by Timeless",
            "all_day": True,
        })
    return events
