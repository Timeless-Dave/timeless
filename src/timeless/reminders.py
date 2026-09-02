from __future__ import annotations

from datetime import datetime, time as dt_time, timedelta, timezone

from timeless.clock import zone


def _morning_utc(on_day, hour: int = 9, minute: int = 0) -> datetime:
    z = zone()
    local = datetime.combine(on_day, dt_time(hour, minute), tzinfo=z)
    return local.astimezone(timezone.utc)


def normalize_fire(purpose: str, fire_at: datetime, event_start: datetime) -> datetime:
    """Keep day-ahead reminders at a sane morning hour instead of arbitrary clock times."""
    if fire_at.tzinfo is None:
        fire_at = fire_at.replace(tzinfo=timezone.utc)
    if event_start.tzinfo is None:
        event_start = event_start.replace(tzinfo=timezone.utc)
    event_local = event_start.astimezone(zone())
    if purpose == "start_1d":
        return _morning_utc(event_local.date() - timedelta(days=1))
    if purpose == "deadline_7d":
        return max(fire_at, _morning_utc(event_local.date() - timedelta(days=7)))
    if purpose == "deadline_1d":
        return max(fire_at, _morning_utc(event_local.date() - timedelta(days=1)))
    return fire_at


def reminder_fires(
    kind: str,
    modality: str,
    start: datetime,
    submit: datetime | None = None,
    present: datetime | None = None,
    now: datetime | None = None,
) -> list[tuple[str, datetime]]:
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    fires: list[tuple[str, datetime]] = []
    if kind == "calendar_note":
        return []
    if kind == "course":
        return [("course_15m", normalize_fire("course_15m", start - timedelta(minutes=15), start))]
    if kind == "deadline":
        return [
            (p, normalize_fire(p, t, start))
            for p, t in [
                ("deadline_7d", start - timedelta(days=7)),
                ("deadline_1d", start - timedelta(days=1)),
                ("deadline_4h", start - timedelta(hours=4)),
            ]
        ]
    if kind == "hackathon":
        fires.append(("start_1d", start - timedelta(days=1)))
        if modality == "virtual":
            fires.append(("start_30m", start - timedelta(minutes=30)))
        else:
            fires.append(("start_2h", start - timedelta(hours=2)))
        if submit:
            fires.append(("submit_4h", submit - timedelta(hours=4)))
        if present:
            fires.append(("present_30m", present - timedelta(minutes=30)))
        return [(p, normalize_fire(p, t, start)) for p, t in fires]
    if modality == "virtual":
        fires.append(("start_30m", start - timedelta(minutes=30)))
        return [(p, normalize_fire(p, t, start)) for p, t in fires]
    fires.append(("start_1d", start - timedelta(days=1)))
    fires.append(("start_2h", start - timedelta(hours=2)))
    return [(p, normalize_fire(p, t, start)) for p, t in fires]
