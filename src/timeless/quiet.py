from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

QUIET_LEVELS = frozenset({"mild", "quiet", "dormant"})
PANIC_MINUTES = 60


def parse_iso(s: str) -> datetime:
    dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def quiet_public(row: dict[str, Any] | None, now: datetime | None = None) -> dict[str, Any] | None:
    if not row:
        return None
    now_dt = now or datetime.now(timezone.utc)
    ends = parse_iso(row["ends_at"])
    starts = parse_iso(row["starts_at"])
    if ends <= now_dt:
        return None
    remaining = int(max(0, (ends - now_dt).total_seconds()))
    return {
        "id": row["id"],
        "active": starts <= now_dt,
        "level": row["level"],
        "starts_at": row["starts_at"],
        "ends_at": row["ends_at"],
        "reason": row.get("reason"),
        "source": row.get("source"),
        "meeting_id": row.get("meeting_id"),
        "goal_id": row.get("goal_id"),
        "seconds_left": remaining,
    }


def blocks_halt(level: str) -> bool:
    return level in {"quiet", "dormant"}


def blocks_phone(level: str) -> bool:
    return level in {"quiet", "dormant"}


def end_from_minutes(minutes: int, now: datetime | None = None) -> str:
    now_dt = now or datetime.now(timezone.utc)
    return iso(now_dt + timedelta(minutes=max(1, minutes)))
