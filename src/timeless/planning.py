"""Feasibility rules for a day's plan.

The gate asks for a commitment; these rules are what make the commitment
credible. Errors block a save, warnings never do — an overloaded day is the
owner's call to make, but they should make it knowingly.
"""
from __future__ import annotations

import re
from typing import Any

TIME = re.compile(r"^(\d{1,2}):(\d{2})$")

# A day this full is almost certainly aspirational rather than planned.
DEFAULT_CAPACITY_MINUTES = 10 * 60
LONG_BLOCK_MINUTES = 4 * 60
BUSY_GOAL_COUNT = 6


def minutes_of_day(value: Any) -> int | None:
    """Minutes since midnight, or None when the time is not HH:MM."""
    match = TIME.match(str(value or "").strip())
    if not match:
        return None
    hours, minutes = int(match.group(1)), int(match.group(2))
    if hours > 23 or minutes > 59:
        return None
    return hours * 60 + minutes


def _span(block: dict[str, Any]) -> tuple[int, int] | None:
    start = minutes_of_day(block.get("start"))
    end = minutes_of_day(block.get("end"))
    if start is None or end is None:
        return None
    return start, end


def block_issues(timeline: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Errors that make a schedule impossible rather than merely ambitious."""
    issues: list[dict[str, Any]] = []
    spans: list[tuple[int, int, int]] = []
    for index, block in enumerate(timeline or []):
        span = _span(block)
        if span is None:
            # Times that are not HH:MM are left alone; older plans used loose values.
            continue
        start, end = span
        if end <= start:
            issues.append(
                {
                    "level": "error",
                    "index": index,
                    "field": "end",
                    "message": f"Block {index + 1} ends before it starts.",
                }
            )
            continue
        spans.append((start, end, index))

    spans.sort()
    for (start, end, index), (next_start, _, next_index) in zip(spans, spans[1:]):
        if next_start < end:
            issues.append(
                {
                    "level": "error",
                    "index": next_index,
                    "field": "start",
                    "message": f"Blocks {index + 1} and {next_index + 1} overlap.",
                }
            )
    return issues


def planned_minutes(timeline: list[dict[str, Any]]) -> int:
    total = 0
    for block in timeline or []:
        span = _span(block)
        if span and span[1] > span[0]:
            total += span[1] - span[0]
    return total


def plan_warnings(
    timeline: list[dict[str, Any]],
    goals: list[dict[str, Any]] | None = None,
    capacity_minutes: int = DEFAULT_CAPACITY_MINUTES,
) -> list[dict[str, Any]]:
    """Things worth knowing before committing. None of these block a save."""
    warnings: list[dict[str, Any]] = []
    total = planned_minutes(timeline)
    if total > capacity_minutes:
        warnings.append(
            {
                "level": "warning",
                "field": "capacity",
                "message": f"{_hours(total)} planned in one day. That is more than most days hold.",
            }
        )
    for index, block in enumerate(timeline or []):
        span = _span(block)
        if span and span[1] - span[0] > LONG_BLOCK_MINUTES:
            warnings.append(
                {
                    "level": "warning",
                    "index": index,
                    "field": "end",
                    "message": f"Block {index + 1} runs {_hours(span[1] - span[0])} without a break.",
                }
            )
    live_goals = [g for g in (goals or []) if str(g.get("text") or "").strip()]
    if len(live_goals) > BUSY_GOAL_COUNT:
        warnings.append(
            {
                "level": "warning",
                "field": "goals",
                "message": f"{len(live_goals)} goals for one day. Consider which ones truly matter.",
            }
        )
    return warnings


def meeting_conflicts(timeline: list[dict[str, Any]], meetings: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """Blocks scheduled over something already on the calendar."""
    conflicts: list[dict[str, Any]] = []
    for index, block in enumerate(timeline or []):
        span = _span(block)
        if not span:
            continue
        start, end = span
        for meeting in meetings or []:
            m_start = _meeting_minutes(meeting.get("start_at"))
            m_end = _meeting_minutes(meeting.get("end_at"))
            if m_start is None or m_end is None:
                continue
            if m_start < end and start < m_end:
                conflicts.append(
                    {
                        "level": "warning",
                        "index": index,
                        "field": "start",
                        "message": f"Block {index + 1} overlaps “{meeting.get('title') or 'a calendar event'}”.",
                    }
                )
                break
    return conflicts


def _meeting_minutes(stamp: Any) -> int | None:
    text = str(stamp or "")
    if "T" not in text:
        return None
    return minutes_of_day(text.split("T", 1)[1][:5])


def _hours(minutes: int) -> str:
    hours = minutes / 60
    label = f"{hours:.1f}".rstrip("0").rstrip(".")
    return f"{label}h"
