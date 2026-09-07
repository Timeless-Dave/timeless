from __future__ import annotations

import json
import re
from contextlib import contextmanager
from functools import wraps
from datetime import datetime, timedelta, timezone
from threading import RLock
from uuid import uuid4
from typing import Any

from timeless.classify_event import URL_RE, classify_event, is_join_url, looks_like_presentation, looks_like_submission, mail_matches_event, pick_join_url
from timeless.clock import day_key, due_recap_day, utc_now, zone
from timeless.db import connect
from timeless.ingest import canonicalize_program_url, classify_screen_text, program_kind_for_url
from timeless.mailer import first_url, parse_when, program_kind
from timeless.planning import block_issues
from timeless.praise import praise_for
from timeless.productivity import classify_activity, productivity_summary
from timeless.quiet import PANIC_MINUTES, QUIET_LEVELS, blocks_halt, end_from_minutes, iso as quiet_iso, parse_iso, quiet_public
from timeless.reminders import reminder_fires

VALID_STATES = frozenset(
    {"seen", "applied", "shortlisted", "interview", "waiting", "offer", "rejected", "skipped", "ignored"}
)
VALID_KINDS = frozenset({"internship", "hackathon", "conference", "other"})
GOAL_STATUSES = frozenset({"planned", "active", "done", "partial", "deferred", "dropped"})
# Still open tomorrow: worth carrying forward.
OPEN_GOAL_STATUSES = frozenset({"planned", "active", "partial", "deferred"})
# Judged by the owner, so they stamp a completion time.
FINISHED_GOAL_STATUSES = frozenset({"done", "partial", "dropped"})
ACTIVITY_BUCKETS = frozenset({"aligned", "productive_off_plan", "distracting", "unknown"})
MEETING_ACKS = frozenset({"join", "im_in"})
EARLY_REMINDER_PURPOSES = frozenset(
    {
        "start_30m",
        "start_2h",
        "start_1d",
        "present_30m",
        "submit_4h",
        "deadline_7d",
        "deadline_1d",
        "deadline_4h",
        "course_15m",
    }
)


class StoreUnavailable(RuntimeError):
    """Raised when the store has been poisoned by a database failure."""


# Recovery and teardown must still work on a poisoned store.
_POISON_SAFE = frozenset({"reconnect", "close", "_poison"})


def _now() -> datetime:
    return utc_now()


def _iso(dt: datetime | None = None) -> str:
    return (dt or _now()).strftime("%Y-%m-%dT%H:%M:%SZ")


def _day(dt: datetime | None = None) -> str:
    return day_key(dt)


def row_to_dict(row) -> dict[str, Any]:
    return dict(row) if row is not None else {}


def _as_index(value: Any) -> int | None:
    """Int or None, without treating a legitimate 0 as absent."""
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value
    text = str(value).strip()
    return int(text) if text.isdigit() else None


def _goal_key(text: str) -> str:
    return " ".join(str(text or "").lower().split())


def _goal_entries(goals: list[Any]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for goal in goals or []:
        if isinstance(goal, str):
            goal = {"text": goal}
        text = str(goal.get("text") or "").strip()
        if not text:
            continue
        status = str(goal.get("status") or "planned")
        if status not in GOAL_STATUSES:
            raise ValueError(f"status must be one of {', '.join(sorted(GOAL_STATUSES))}")
        raw_id = goal.get("id")
        entries.append(
            {
                "id": int(raw_id) if isinstance(raw_id, int) or str(raw_id or "").isdigit() else None,
                "text": text[:400],
                "status": status,
                "note": (str(goal.get("note") or "").strip() or None),
                "carried_from": int(goal["carried_from"]) if str(goal.get("carried_from") or "").isdigit() else None,
            }
        )
    return entries


def _goal_entries_from_outcomes(outcomes: str) -> list[dict[str, Any]]:
    lines = [
        re.sub(r"^\s*(?:[-\u2022]|\d+[.)])\s*", "", line).strip()
        for line in re.split(r"[\n;]+", outcomes or "")
    ]
    return _goal_entries([line for line in lines if line])


def _link_blocks(
    timeline: list[dict],
    goals: list[dict[str, Any]],
    previous: list[dict] | None = None,
) -> list[dict]:
    """Resolve each block's goal reference to a stored goal id.

    New goals have no id until they are written, so the editor points at them by
    position; existing ones may be referenced by id directly.
    """
    valid = {goal["id"] for goal in goals}
    # Safety net for clients that do not echo block_id back: an unchanged block
    # inherits the identity of the stored one it exactly matches, so its run
    # history is not orphaned. Ambiguous matches are left to mint a new id.
    inheritable = _unique_block_ids(previous or [])
    claimed: set[str] = {
        str(block.get("block_id")) for block in timeline if str(block.get("block_id") or "").strip()
    }
    linked = []
    for block in timeline:
        block = dict(block)
        # A block keeps its id across saves so its run survives an edit.
        if not str(block.get("block_id") or "").strip():
            inherited = inheritable.get(_block_signature(block))
            if inherited and inherited not in claimed:
                block["block_id"] = inherited
                claimed.add(inherited)
            else:
                block["block_id"] = uuid4().hex[:12]
        goal_id = block.pop("goal_id", None)
        index = block.pop("goal_index", None)
        resolved = None
        if _as_index(goal_id) in valid:
            resolved = _as_index(goal_id)
        elif 0 <= (_as_index(index) if _as_index(index) is not None else -1) < len(goals):
            resolved = goals[_as_index(index)]["id"]
        if resolved is not None:
            block["goal_id"] = resolved
        linked.append(block)
    return linked


def _run_seconds(row) -> float:
    """Accumulated time including the stretch currently running."""
    total = float(row["accumulated_seconds"] or 0)
    if row["state"] == "running" and row["resumed_at"]:
        started = datetime.strptime(row["resumed_at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        total += max(0.0, (_now() - started).total_seconds())
    return round(total, 1)


def _block_run_public(row) -> dict[str, Any]:
    data = row_to_dict(row)
    data["elapsed_seconds"] = _run_seconds(row)
    return data


def _goal_has_history(goal: dict[str, Any]) -> bool:
    """Whether anything happened to this goal that is worth keeping."""
    return bool(
        (goal.get("status") or "planned") != "planned"
        or goal.get("note")
        or goal.get("completed_at")
        or goal.get("carried_from")
    )


def _headline_goal(goals: list[dict[str, Any]]) -> dict[str, Any] | None:
    """The one goal the day is pointed at. Deferred work is never picked up
    automatically; pushing something away should not hand it straight back."""
    for status in ("active", "planned", "partial"):
        match = next((g for g in goals if (g.get("status") or "planned") == status), None)
        if match:
            return match
    return None


def _minutes_of_day(value: Any) -> int | None:
    match = re.match(r"^(\d{1,2}):(\d{2})$", str(value or "").strip())
    if not match:
        return None
    hours, minutes = int(match.group(1)), int(match.group(2))
    return hours * 60 + minutes if hours <= 23 and minutes <= 59 else None


def _local_minute() -> int:
    local = _now().astimezone(zone())
    return local.hour * 60 + local.minute


def _block_is_over(block: dict[str, Any]) -> bool:
    end = _minutes_of_day(block.get("end"))
    return end is not None and _local_minute() >= end


def _next_block(timeline: list[dict]) -> dict[str, Any] | None:
    minute = _local_minute()
    upcoming = [
        (start, block)
        for block in timeline
        for start in [_minutes_of_day(block.get("start"))]
        if start is not None and start > minute
    ]
    return min(upcoming, key=lambda pair: pair[0])[1] if upcoming else None


def _block_signature(block: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(block.get("start") or "").strip(),
        str(block.get("end") or "").strip(),
        str(block.get("task") or "").strip().lower(),
    )


def _unique_block_ids(previous: list[dict]) -> dict[tuple[str, str, str], str]:
    """Signatures that identify exactly one stored block."""
    seen: dict[tuple[str, str, str], list[str]] = {}
    for block in previous:
        block_id = str(block.get("block_id") or "").strip()
        if block_id:
            seen.setdefault(_block_signature(block), []).append(block_id)
    return {signature: ids[0] for signature, ids in seen.items() if len(ids) == 1}


def goal_progress(goals: list[dict[str, Any]]) -> dict[str, Any]:
    """Explicit completion counts, kept separate from any activity estimate."""
    counts = {status: 0 for status in sorted(GOAL_STATUSES)}
    for goal in goals or []:
        status = str(goal.get("status") or "planned")
        if status in counts:
            counts[status] += 1
    total = sum(counts.values())
    counted = total - counts["dropped"]
    return {
        "total": total,
        # Dropped work is not a failure, so it leaves the denominator here and
        # in `percent` alike; the UI counts against `counted`, never `total`.
        "counted": counted,
        "counts": counts,
        "done": counts["done"],
        "partial": counts["partial"],
        "open": counts["planned"] + counts["active"] + counts["deferred"],
        "active": counts["active"],
        "percent": round(100 * (counts["done"] + 0.5 * counts["partial"]) / counted) if counted else None,
    }


class Store:
    def __init__(self, db_path: str):
        # FastAPI runs synchronous endpoints in a worker pool while the Mac
        # sensors ingest concurrently. A sqlite connection may be shared only
        # when every complete Store operation is serialized.
        self._lock = RLock()
        self._in_atomic = False
        self._poisoned = False
        self.db_path = db_path
        self.conn = connect(db_path)

    def close(self) -> None:
        self.conn.close()

    def _commit(self) -> None:
        """Commit, unless a surrounding operation owns the transaction."""
        if not self._in_atomic:
            self.conn.commit()

    @contextmanager
    def _atomic(self):
        """Run several store operations as one unit.

        The individual methods commit as they go, which is correct when they are
        called alone. Inside this block their commits are suppressed and the work
        sits on a savepoint, so a failure part-way cannot leave the goal changed
        but the focus session unreconciled.
        """
        if self._in_atomic:
            yield
            return
        self._in_atomic = True
        # Only a clean finish earns a commit. Anything else discards the whole
        # transaction: committing after a failed undo is how half a change gets
        # written, which is the one outcome this block exists to prevent.
        settled = False
        try:
            # Opening the savepoint is inside the guard too: if the database
            # fails here, the flag must still clear, or every later write would
            # stay uncommitted until restart.
            self.conn.execute("SAVEPOINT store_atomic")
            try:
                yield
            except BaseException:
                self.conn.execute("ROLLBACK TO SAVEPOINT store_atomic")
                self.conn.execute("RELEASE SAVEPOINT store_atomic")
                # The block's writes are undone, so the transaction holds only
                # what was already there and is safe to close normally.
                settled = True
                raise
            self.conn.execute("RELEASE SAVEPOINT store_atomic")
            settled = True
        finally:
            self._in_atomic = False
            self._close_transaction(settled)

    def _close_transaction(self, settled: bool) -> None:
        """Commit a settled transaction, otherwise discard it.

        A failure while unwinding leaves the savepoint state unknown, so the
        only safe move is to throw the whole transaction away rather than
        persist whatever happens to be in it.
        """
        if settled:
            try:
                self.conn.commit()
            except BaseException:
                # A commit that failed did not happen. Reporting success for
                # work that is not on disk would be worse than the failure.
                self._poison()
                raise
            return
        try:
            self.conn.rollback()
        except BaseException:
            # The abandoned writes are still sitting in an open transaction, so
            # the next ordinary commit would publish them. The connection cannot
            # be trusted and is discarded rather than left to leak them later.
            self._poison()
            raise

    def _poison(self) -> None:
        """Refuse further work on a connection that cannot be unwound.

        Closing discards any open transaction, so the abandoned writes never
        reach the file. The store stays unusable until `reconnect`, because
        quietly carrying on after a database failure is how a partial change
        gets published by an unrelated write minutes later.
        """
        self._poisoned = True
        self._in_atomic = False
        try:
            self.conn.close()
        except BaseException:
            pass

    def reconnect(self) -> None:
        """Recover a poisoned store on a fresh connection.

        Whatever the failed transaction held was never committed, so this
        resumes from the last consistent state on disk.
        """
        try:
            self.conn.close()
        except BaseException:
            pass
        self.conn = connect(self.db_path)
        self._in_atomic = False
        self._poisoned = False

    @property
    def poisoned(self) -> bool:
        return self._poisoned

    def heartbeat(self, sensor: str, detail: str | None = None) -> None:
        self.conn.execute(
            """
            INSERT INTO heartbeats(sensor, last_seen, detail) VALUES (?, ?, ?)
            ON CONFLICT(sensor) DO UPDATE SET last_seen=excluded.last_seen, detail=excluded.detail
            """,
            (sensor, _iso(), detail),
        )
        self._commit()

    def heartbeats(self) -> list[dict[str, Any]]:
        return [row_to_dict(r) for r in self.conn.execute("SELECT * FROM heartbeats ORDER BY sensor")]

    def add_event(self, source: str, summary: str, payload: dict | None = None) -> int:
        cur = self.conn.execute(
            "INSERT INTO events(source, ts, summary, payload) VALUES (?, ?, ?, ?)",
            (source, _iso(), summary, json.dumps(payload or {})),
        )
        self._commit()
        return int(cur.lastrowid)

    def add_activity(
        self,
        *,
        source: str,
        source_id: str,
        ts: str,
        duration_seconds: float,
        app: str | None = None,
        host: str | None = None,
        title: str | None = None,
    ) -> dict[str, Any]:
        timestamp = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        category, productivity = classify_activity(app, title, host)
        self.conn.execute(
            """INSERT INTO activity_samples(source, source_id, ts, duration_seconds, app, host, title, category, productivity)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(source, source_id) DO UPDATE SET
                 ts=excluded.ts, duration_seconds=excluded.duration_seconds, app=excluded.app,
                 host=excluded.host, title=excluded.title, category=excluded.category,
                 productivity=excluded.productivity""",
            (source[:40], source_id[:240], _iso(timestamp), max(0.0, min(float(duration_seconds), 86400.0)), (app or "")[:120], (host or "")[:200], (title or "")[:240], category, productivity),
        )
        self._commit()
        row = self.conn.execute("SELECT * FROM activity_samples WHERE source=? AND source_id=?", (source[:40], source_id[:240])).fetchone()
        return row_to_dict(row)

    def activities_on_day(self, day: str) -> list[dict[str, Any]]:
        try:
            local_start = datetime.strptime(day, "%Y-%m-%d").replace(tzinfo=zone())
        except ValueError:
            return []
        start = _iso(local_start.astimezone(timezone.utc))
        end = _iso((local_start + timedelta(days=1)).astimezone(timezone.utc))
        return [row_to_dict(row) for row in self.conn.execute("SELECT * FROM activity_samples WHERE ts>=? AND ts<? ORDER BY ts", (start, end))]

    def productivity_on_day(self, day: str) -> dict[str, Any]:
        return productivity_summary(
            self.activities_on_day(day),
            self.get_plan(day),
            corrections=self.activity_corrections(day),
        )

    def latest_event_age_seconds(self) -> float | None:
        row = self.conn.execute("SELECT ts FROM events ORDER BY ts DESC LIMIT 1").fetchone()
        if not row:
            return None
        ts = datetime.strptime(row["ts"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        return (_now() - ts).total_seconds()

    def save_plan(
        self,
        outcomes: str,
        timeline: list[dict],
        day: str | None = None,
        goals: list[dict] | None = None,
    ) -> dict[str, Any]:
        """Persist a day's plan.

        ``goals`` is the structured form and wins when supplied; ``outcomes``
        stays as its newline-joined projection so the recap, chat snapshot and
        legacy overlay pages keep reading the same field they always have.
        """
        entries = _goal_entries(goals) if goals is not None else _goal_entries_from_outcomes(outcomes)
        if not entries:
            raise ValueError("outcomes required")
        for block in timeline:
            if not str(block.get("task") or "").strip():
                raise ValueError("each block needs a task")
        issues = block_issues(timeline)
        if issues:
            raise ValueError("; ".join(issue["message"] for issue in issues))
        day = day or _day()
        now = _iso()
        previous = (self.get_plan(day) or {}).get("timeline") or []
        stored_goals = self._sync_goals(day, entries, now)
        outcomes = "\n".join(goal["text"] for goal in stored_goals)
        payload = json.dumps(_link_blocks(timeline, stored_goals, previous))
        existing = self.conn.execute("SELECT id FROM daily_plans WHERE day=?", (day,)).fetchone()
        if existing:
            self.conn.execute(
                "UPDATE daily_plans SET outcomes=?, timeline=?, updated_at=? WHERE day=?",
                (outcomes, payload, now, day),
            )
        else:
            self.conn.execute(
                """
                INSERT INTO daily_plans(day, outcomes, timeline, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (day, outcomes, payload, now, now),
            )
        self._mark_carried_sources(stored_goals, now)
        self._commit()
        return self.get_plan(day)

    def get_plan(self, day: str | None = None) -> dict[str, Any] | None:
        day = day or _day()
        row = self.conn.execute("SELECT * FROM daily_plans WHERE day=?", (day,)).fetchone()
        if not row:
            return None
        data = row_to_dict(row)
        data["timeline"] = json.loads(data["timeline"])
        data["goals"] = self.list_goals(day)
        data["goal_progress"] = goal_progress(data["goals"])
        data["block_runs"] = self.block_runs(day)
        return data

    def list_goals(self, day: str | None = None, include_archived: bool = False) -> list[dict[str, Any]]:
        day = day or _day()
        clause = "" if include_archived else " AND archived_at IS NULL"
        rows = self.conn.execute(
            f"SELECT * FROM plan_goals WHERE day=?{clause} ORDER BY position, id", (day,)
        ).fetchall()
        return [self._goal_public(row_to_dict(row)) for row in rows]

    def archived_goals(self, day: str | None = None) -> list[dict[str, Any]]:
        day = day or _day()
        rows = self.conn.execute(
            "SELECT * FROM plan_goals WHERE day=? AND archived_at IS NOT NULL ORDER BY position, id", (day,)
        ).fetchall()
        return [self._goal_public(row_to_dict(row)) for row in rows]

    def restore_goal(self, goal_id: int) -> dict[str, Any]:
        """Bring an archived goal back into its day."""
        row = self.conn.execute("SELECT * FROM plan_goals WHERE id=?", (int(goal_id),)).fetchone()
        if not row:
            raise ValueError("unknown goal")
        now = _iso()
        self.conn.execute(
            "UPDATE plan_goals SET archived_at=NULL, updated_at=? WHERE id=?", (now, int(goal_id))
        )
        self._commit()
        plan = self.get_plan(row["day"])
        if plan:
            outcomes = "\n".join(goal["text"] for goal in plan["goals"])
            self.conn.execute(
                "UPDATE daily_plans SET outcomes=?, updated_at=? WHERE day=?", (outcomes, now, row["day"])
            )
            self._commit()
        return self.get_goal(goal_id)

    def get_goal(self, goal_id: int) -> dict[str, Any] | None:
        row = self.conn.execute("SELECT * FROM plan_goals WHERE id=?", (int(goal_id),)).fetchone()
        return self._goal_public(row_to_dict(row)) if row else None

    def set_goal_status(self, goal_id: int, status: str, note: str | None = None) -> dict[str, Any]:
        """Record an explicit human judgement about a goal.

        This is the authoritative progress signal; observed activity only ever
        supports it. At most one goal per day is ``active`` so "what am I doing
        now" has a single answer.
        """
        if status not in GOAL_STATUSES:
            raise ValueError(f"status must be one of {', '.join(sorted(GOAL_STATUSES))}")
        row = self.conn.execute("SELECT * FROM plan_goals WHERE id=?", (int(goal_id),)).fetchone()
        if not row:
            raise ValueError("unknown goal")
        now = _iso()
        completed_at = now if status in FINISHED_GOAL_STATUSES else None
        if status == "active":
            self.conn.execute(
                "UPDATE plan_goals SET status='planned', updated_at=? WHERE day=? AND status='active' AND id<>?",
                (now, row["day"], int(goal_id)),
            )
        if note is None:
            # Absent means "leave the existing note"; an empty string clears it.
            self.conn.execute(
                "UPDATE plan_goals SET status=?, completed_at=?, updated_at=? WHERE id=?",
                (status, completed_at, now, int(goal_id)),
            )
        else:
            self.conn.execute(
                "UPDATE plan_goals SET status=?, note=?, completed_at=?, updated_at=? WHERE id=?",
                (status, note.strip() or None, completed_at, now, int(goal_id)),
            )
        self._commit()
        self.add_event("goal", f"{status}: {row['text']}", {"goal_id": int(goal_id), "day": row["day"]})
        return self.get_goal(goal_id)

    def start_block(self, day: str, block_id: str, goal_id: int | None = None) -> dict[str, Any]:
        """Begin (or resume) a block. Only one block runs at a time per day."""
        now = _iso()
        self._pause_running(day, now, except_block=block_id)
        row = self._block_run_row(day, block_id)
        if row and row["state"] == "done":
            raise ValueError("block already finished")
        if row:
            if row["state"] == "running":
                return self.block_run(day, block_id)
            self.conn.execute(
                "UPDATE block_runs SET state='running', resumed_at=?, goal_id=COALESCE(?, goal_id), updated_at=? WHERE id=?",
                (now, goal_id, now, row["id"]),
            )
        else:
            self.conn.execute(
                """
                INSERT INTO block_runs(day, block_id, goal_id, state, started_at, resumed_at, updated_at)
                VALUES (?, ?, ?, 'running', ?, ?, ?)
                """,
                (day, block_id, goal_id, now, now, now),
            )
        self._commit()
        return self.block_run(day, block_id)

    def pause_block(self, day: str, block_id: str) -> dict[str, Any]:
        row = self._block_run_row(day, block_id)
        if not row:
            raise ValueError("block was never started")
        if row["state"] != "running":
            return self.block_run(day, block_id)
        now = _iso()
        self.conn.execute(
            "UPDATE block_runs SET state='paused', accumulated_seconds=?, resumed_at=NULL, updated_at=? WHERE id=?",
            (_run_seconds(row), now, row["id"]),
        )
        self._commit()
        return self.block_run(day, block_id)

    def finish_block(self, day: str, block_id: str) -> dict[str, Any]:
        row = self._block_run_row(day, block_id)
        now = _iso()
        if not row:
            # Finishing something never started still records that it is done.
            self.conn.execute(
                """
                INSERT INTO block_runs(day, block_id, state, started_at, ended_at, updated_at)
                VALUES (?, ?, 'done', ?, ?, ?)
                """,
                (day, block_id, now, now, now),
            )
        else:
            self.conn.execute(
                "UPDATE block_runs SET state='done', accumulated_seconds=?, ended_at=?, resumed_at=NULL, updated_at=? WHERE id=?",
                (_run_seconds(row), now, now, row["id"]),
            )
        self._commit()
        return self.block_run(day, block_id)

    def block_run(self, day: str, block_id: str) -> dict[str, Any] | None:
        row = self._block_run_row(day, block_id)
        return _block_run_public(row) if row else None

    def block_runs(self, day: str | None = None) -> list[dict[str, Any]]:
        day = day or _day()
        return [
            _block_run_public(row)
            for row in self.conn.execute("SELECT * FROM block_runs WHERE day=? ORDER BY id", (day,))
        ]

    def _block_run_row(self, day: str, block_id: str):
        return self.conn.execute(
            "SELECT * FROM block_runs WHERE day=? AND block_id=?", (day, block_id)
        ).fetchone()

    def _pause_running(self, day: str, now: str, except_block: str | None = None) -> None:
        for row in self.conn.execute(
            "SELECT * FROM block_runs WHERE day=? AND state='running'", (day,)
        ).fetchall():
            if except_block and row["block_id"] == except_block:
                continue
            self.conn.execute(
                "UPDATE block_runs SET state='paused', accumulated_seconds=?, resumed_at=NULL, updated_at=? WHERE id=?",
                (_run_seconds(row), now, row["id"]),
            )

    def active_work(self, day: str | None = None) -> dict[str, Any]:
        """The single answer to "what am I doing now".

        Goal, block and focus are stored separately and can drift apart; this
        reconciles them into one view and names the disagreements rather than
        leaving the owner to spot them.
        """
        day = day or _day()
        plan = self.get_plan(day) or {}
        goals = {int(goal["id"]): goal for goal in plan.get("goals") or []}
        timeline = plan.get("timeline") or []
        blocks = {str(b.get("block_id")): b for b in timeline if b.get("block_id")}
        runs = {run["block_id"]: run for run in self.block_runs(day)}
        quiet = self.quiet_summary()

        goal = _headline_goal(plan.get("goals") or [])
        running = next((run for run in runs.values() if run["state"] == "running"), None)
        running_block = blocks.get(running["block_id"]) if running else None
        scheduled = self._scheduled_block(timeline)

        conflicts: list[dict[str, Any]] = []
        if running_block and _block_is_over(running_block):
            conflicts.append(
                {
                    "kind": "stale_block",
                    "action": "finish_block",
                    "block_id": running_block["block_id"],
                    "message": f"“{running_block.get('task')}” is still running past its scheduled end.",
                }
            )
        if running_block and scheduled and running_block["block_id"] != scheduled.get("block_id"):
            conflicts.append(
                {
                    "kind": "off_schedule",
                    # The fix is to move to what the schedule says, not to end
                    # the work the owner deliberately chose.
                    "action": "switch_work",
                    "block_id": scheduled.get("block_id"),
                    "goal_id": scheduled.get("goal_id"),
                    "message": (
                        f"You are running “{running_block.get('task')}”, "
                        f"but “{scheduled.get('task')}” is scheduled now."
                    ),
                }
            )
        running_goal_id = running_block.get("goal_id") if running_block else None
        if running_goal_id and goal and int(running_goal_id) != int(goal["id"]):
            conflicts.append(
                {
                    "kind": "goal_mismatch",
                    "action": "switch_work",
                    "goal_id": int(running_goal_id),
                    "message": (
                        f"The running block serves “{goals.get(int(running_goal_id), {}).get('text', 'another goal')}”, "
                        f"but “{goal['text']}” is marked active."
                    ),
                }
            )
        if (
            not running_block
            and scheduled
            and goal
            and scheduled.get("goal_id")
            and int(scheduled["goal_id"]) != int(goal["id"])
        ):
            conflicts.append(
                {
                    "kind": "scheduled_elsewhere",
                    "action": "switch_work",
                    "goal_id": int(scheduled["goal_id"]),
                    "block_id": scheduled.get("block_id"),
                    "message": (
                        f"“{scheduled.get('task')}” is scheduled now, but it serves "
                        f"“{goals.get(int(scheduled['goal_id']), {}).get('text', 'another goal')}”."
                    ),
                }
            )
        focus_goal_id = quiet.get("goal_id") if quiet and quiet.get("active") else None
        if focus_goal_id and goal and int(focus_goal_id) != int(goal["id"]):
            conflicts.append(
                {
                    "kind": "focus_mismatch",
                    "action": "switch_work",
                    "goal_id": int(focus_goal_id),
                    "message": (
                        f"Focus is protecting “{goals.get(int(focus_goal_id), {}).get('text', 'another goal')}”, "
                        f"not “{goal['text']}”."
                    ),
                }
            )

        return {
            "day": day,
            "goal": goal,
            "running_block": dict(running_block, run=running) if running_block else None,
            "scheduled_block": scheduled,
            "focus": quiet if quiet and quiet.get("active") else None,
            "next_action": self._next_action(goal, timeline, running_block),
            "conflicts": conflicts,
        }

    def _next_action(
        self,
        goal: dict[str, Any] | None,
        timeline: list[dict],
        running_block: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        """The single concrete next step, always for the headline goal.

        Derived here rather than in the interface so the goal on screen and the
        action beneath it can never describe different work.
        """
        if not goal:
            return None
        minute = _local_minute()
        if running_block:
            end = _minutes_of_day(running_block.get("end"))
            return {
                "text": running_block.get("task") or goal["text"],
                "source": "running_block",
                "block_id": running_block.get("block_id"),
                "minutes_left": max(0, end - minute) if end is not None else None,
            }
        mine = [b for b in timeline if b.get("goal_id") and int(b["goal_id"]) == int(goal["id"])]
        covering = self._scheduled_block(mine)
        if covering:
            end = _minutes_of_day(covering.get("end"))
            return {
                "text": covering.get("task") or goal["text"],
                "source": "scheduled_block",
                "block_id": covering.get("block_id"),
                "minutes_left": max(0, end - minute) if end is not None else None,
            }
        upcoming = _next_block(mine)
        if upcoming:
            return {
                "text": upcoming.get("task") or goal["text"],
                "source": "upcoming_block",
                "block_id": upcoming.get("block_id"),
                "starts_at": upcoming.get("start"),
            }
        return {"text": goal["text"], "source": "goal"}

    def start_work(
        self,
        day: str | None = None,
        goal_id: int | None = None,
        block_id: str | None = None,
        focus_minutes: int | None = None,
        focus_level: str = "quiet",
    ) -> dict[str, Any]:
        """Point goal, block and focus at the same work in one move."""
        day = day or _day()
        plan = self.get_plan(day) or {}
        timeline = plan.get("timeline") or []

        if block_id and goal_id is None:
            block = next((b for b in timeline if str(b.get("block_id")) == str(block_id)), None)
            if block and block.get("goal_id"):
                goal_id = int(block["goal_id"])
        if goal_id and not block_id:
            # Prefer a block for this goal covering now, else its next one.
            candidates = [b for b in timeline if b.get("goal_id") and int(b["goal_id"]) == int(goal_id)]
            covering = self._scheduled_block(candidates)
            upcoming = _next_block(candidates)
            chosen = covering or upcoming
            if chosen:
                block_id = str(chosen["block_id"])

        with self._atomic():
            if goal_id is not None:
                self.set_goal_status(int(goal_id), "active")
            if block_id:
                run = self.block_run(day, block_id)
                if not run or run["state"] != "done":
                    self.start_block(day, block_id, goal_id)
            else:
                # Nothing to run, but a block left over from earlier must not keep ticking.
                self._pause_running(day, _iso())
            self._rebind_focus(goal_id, focus_minutes, focus_level)
        return self.active_work(day)

    def _rebind_focus(self, goal_id: int | None, focus_minutes: int | None, focus_level: str) -> None:
        """Point the focus session at the work that is now current.

        Switching goals must never leave the previous goal's session running:
        detecting that afterwards as a conflict would be a contradiction this
        method caused. Protection carries over with its remaining time.
        """
        existing = self.quiet_summary()
        active = existing if existing and existing.get("active") else None
        goal = self.get_goal(int(goal_id)) if goal_id is not None else None

        if active and active.get("goal_id") is not None and goal_id is not None:
            if int(active["goal_id"]) == int(goal_id):
                return
        if active is None and not focus_minutes:
            return

        minutes = focus_minutes
        if active:
            if minutes is None:
                # Carry the remaining protection across rather than dropping it.
                minutes = max(1, round((active.get("seconds_left") or 0) / 60))
            focus_level = active.get("level") or focus_level
            self.end_quiet(int(active["id"]))
        if goal_id is None:
            # Work with no goal to protect: the old session simply ends.
            return
        self.create_quiet(
            level=focus_level,
            minutes=minutes,
            reason=(goal or {}).get("text"),
            source="work",
            goal_id=int(goal_id),
        )

    def stop_work(self, day: str | None = None, end_focus: bool = True) -> dict[str, Any]:
        """Put the day down without judging any goal."""
        day = day or _day()
        with self._atomic():
            self._pause_running(day, _iso())
            if end_focus:
                quiet = self.quiet_summary()
                if quiet and quiet.get("active") and quiet.get("id"):
                    self.end_quiet(int(quiet["id"]))
        return self.active_work(day)

    def _scheduled_block(self, timeline: list[dict]) -> dict[str, Any] | None:
        minute = _local_minute()
        for block in timeline:
            start = _minutes_of_day(block.get("start"))
            end = _minutes_of_day(block.get("end"))
            if start is not None and end is not None and start <= minute < end:
                return block
        return None

    def carry_forward_candidates(self, day: str | None = None) -> list[dict[str, Any]]:
        """Unfinished goals from the last planned day before ``day``."""
        day = day or _day()
        previous = self.conn.execute(
            "SELECT day FROM daily_plans WHERE day<? ORDER BY day DESC LIMIT 1", (day,)
        ).fetchone()
        if not previous:
            return []
        already = {
            row["carried_from"]
            for row in self.conn.execute(
                "SELECT carried_from FROM plan_goals WHERE day=? AND carried_from IS NOT NULL", (day,)
            )
        }
        return [
            goal
            for goal in self.list_goals(previous["day"])
            if goal["status"] in OPEN_GOAL_STATUSES and goal["id"] not in already
        ]

    def _goal_public(self, goal: dict[str, Any]) -> dict[str, Any]:
        goal["deferred_count"] = self._deferral_depth(goal.get("carried_from"))
        return goal

    def _deferral_depth(self, carried_from: int | None) -> int:
        depth = 0
        seen: set[int] = set()
        while carried_from and carried_from not in seen and depth < 60:
            seen.add(int(carried_from))
            row = self.conn.execute(
                "SELECT carried_from FROM plan_goals WHERE id=?", (int(carried_from),)
            ).fetchone()
            depth += 1
            carried_from = row["carried_from"] if row else None
        return depth

    def _sync_goals(self, day: str, entries: list[dict[str, Any]], now: str) -> list[dict[str, Any]]:
        """Reconcile the submitted goal list against the stored rows for ``day``.

        Rows are matched by id, then by text, so re-saving a plan never resets
        the status of a goal that has already been worked on.
        """
        existing = {
            int(row["id"]): row_to_dict(row)
            for row in self.conn.execute(
                "SELECT * FROM plan_goals WHERE day=? AND archived_at IS NULL", (day,)
            )
        }
        by_text: dict[str, list[int]] = {}
        for goal_id, row in sorted(existing.items()):
            by_text.setdefault(_goal_key(row["text"]), []).append(goal_id)
        kept: list[int] = []
        for position, entry in enumerate(entries):
            goal_id = entry["id"] if entry["id"] in existing else None
            if goal_id is None:
                bucket = by_text.get(_goal_key(entry["text"]), [])
                while bucket:
                    candidate = bucket.pop(0)
                    if candidate not in kept:
                        goal_id = candidate
                        break
            if goal_id is None:
                cursor = self.conn.execute(
                    """
                    INSERT INTO plan_goals(day, text, position, status, note, carried_from, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (day, entry["text"], position, entry["status"], entry["note"], entry["carried_from"], now, now),
                )
                kept.append(int(cursor.lastrowid))
                continue
            self.conn.execute(
                "UPDATE plan_goals SET text=?, position=?, note=COALESCE(?, note), updated_at=? WHERE id=?",
                (entry["text"], position, entry["note"], now, goal_id),
            )
            kept.append(goal_id)
        for goal_id in [gid for gid in existing if gid not in kept]:
            row = existing[goal_id]
            if _goal_has_history(row):
                # Removing a goal from the editor must not erase what happened to
                # it; a longitudinal record is the point of storing goals at all.
                self.conn.execute(
                    "UPDATE plan_goals SET archived_at=?, updated_at=? WHERE id=?", (now, now, goal_id)
                )
            else:
                self.conn.execute("DELETE FROM plan_goals WHERE id=?", (goal_id,))
        return self.list_goals(day)

    def _mark_carried_sources(self, goals: list[dict[str, Any]], now: str) -> None:
        """A goal pulled into a later day leaves its source explicitly deferred."""
        sources = [goal["carried_from"] for goal in goals if goal.get("carried_from")]
        if not sources:
            return
        self.conn.executemany(
            "UPDATE plan_goals SET status='deferred', updated_at=? WHERE id=? AND status IN ('planned','active')",
            [(now, int(source)) for source in sources],
        )

    def add_ritual(
        self,
        name: str,
        launch_url: str | None = None,
        app_bundle: str | None = None,
        weekdays: str = "1,2,3,4,5",
        match_host: str | None = None,
        min_minutes: int | None = None,
    ) -> int:
        cur = self.conn.execute(
            """
            INSERT INTO rituals(name, launch_url, app_bundle, weekdays, match_host, min_minutes)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (name, launch_url, app_bundle, weekdays, match_host, min_minutes),
        )
        self._commit()
        return int(cur.lastrowid)

    def list_rituals(self) -> list[dict[str, Any]]:
        return [row_to_dict(r) for r in self.conn.execute("SELECT * FROM rituals ORDER BY id")]

    def complete_ritual(self, ritual_id: int, day: str | None = None) -> dict[str, Any]:
        day = day or _day()
        ritual = self.conn.execute("SELECT * FROM rituals WHERE id=?", (ritual_id,)).fetchone()
        if not ritual:
            raise ValueError("unknown ritual")
        praise = praise_for(ritual["name"])
        try:
            self.conn.execute(
                "INSERT INTO ritual_completions(ritual_id, day, praise, created_at) VALUES (?, ?, ?, ?)",
                (ritual_id, day, praise, _iso()),
            )
        except Exception as exc:
            raise ValueError("already completed today") from exc
        self._commit()
        return {"ritual_id": ritual_id, "day": day, "praise": praise}

    def upsert_opportunity(
        self,
        *,
        url: str,
        company: str | None = None,
        role: str | None = None,
        state: str = "seen",
        kind: str = "internship",
        deadline_at: str | None = None,
        source: str = "url",
    ) -> dict[str, Any]:
        if url.startswith(("http://", "https://")):
            url = canonicalize_program_url(url)
        if state not in VALID_STATES:
            raise ValueError("bad state")
        if kind not in VALID_KINDS:
            raise ValueError("bad kind")
        now = _iso()
        row = self.conn.execute("SELECT * FROM opportunities WHERE url=?", (url,)).fetchone()
        if row:
            self.conn.execute(
                """
                UPDATE opportunities SET company=COALESCE(?, company), role=COALESCE(?, role),
                    deadline_at=COALESCE(?, deadline_at), kind=COALESCE(?, kind), updated_at=?
                WHERE id=?
                """,
                (company, role, deadline_at, kind, now, row["id"]),
            )
            self._commit()
            out = row_to_dict(self.conn.execute("SELECT * FROM opportunities WHERE id=?", (row["id"],)).fetchone())
            self.set_setting("google_tracker_dirty", "1")
            self._sync_opportunity_deadline(out)
            return out
        cur = self.conn.execute(
            """
            INSERT INTO opportunities(company, role, url, state, kind, deadline_at, source, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (company, role, url, state, kind, deadline_at, source, now, now),
        )
        self._commit()
        out = row_to_dict(self.conn.execute("SELECT * FROM opportunities WHERE id=?", (cur.lastrowid,)).fetchone())
        self.set_setting("google_tracker_dirty", "1")
        self._sync_opportunity_deadline(out)
        return out

    def _sync_opportunity_deadline(self, opportunity: dict[str, Any]) -> None:
        uid = f"opportunity:{opportunity['id']}:deadline"
        raw = (opportunity.get("deadline_at") or "").strip()
        if not raw:
            self.conn.execute("DELETE FROM reminders WHERE event_uid=?", (uid,))
            self.conn.execute("DELETE FROM meetings WHERE uid=?", (uid,))
            self._commit()
            return
        try:
            deadline = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return
        if deadline.tzinfo is None:
            if len(raw) == 10:
                deadline = deadline.replace(hour=17, minute=0)
            deadline = deadline.replace(tzinfo=zone())
        deadline = deadline.astimezone(timezone.utc)
        self.upsert_meeting(
            uid=uid,
            title=f"Deadline · {opportunity.get('role') or opportunity.get('company') or 'Program'}",
            start_at=_iso(deadline),
            end_at=_iso(deadline + timedelta(minutes=30)),
            notes=opportunity.get("url"),
            kind="deadline",
            modality="virtual",
            reminder_only=True,
        )

    def set_opportunity_state(self, opportunity_id: int, state: str, kind: str | None = None) -> dict[str, Any]:
        if state not in VALID_STATES:
            raise ValueError("bad state")
        if kind:
            if kind not in VALID_KINDS:
                raise ValueError("bad kind")
            self.conn.execute("UPDATE opportunities SET kind=? WHERE id=?", (kind, opportunity_id))
        self.conn.execute(
            "UPDATE opportunities SET state=?, updated_at=? WHERE id=?",
            (state, _iso(), opportunity_id),
        )
        self._commit()
        row = self.conn.execute("SELECT * FROM opportunities WHERE id=?", (opportunity_id,)).fetchone()
        if not row:
            raise ValueError("unknown opportunity")
        self.set_setting("google_tracker_dirty", "1")
        return row_to_dict(row)

    def patch_opportunity(
        self,
        opportunity_id: int,
        *,
        company: str | None = None,
        role: str | None = None,
        kind: str | None = None,
        url: str | None = None,
        deadline_at: str | None = None,
    ) -> dict[str, Any]:
        row = self.conn.execute("SELECT * FROM opportunities WHERE id=?", (opportunity_id,)).fetchone()
        if not row:
            raise ValueError("unknown opportunity")
        if kind is not None and kind not in VALID_KINDS:
            raise ValueError("bad kind")
        self.conn.execute(
            """
            UPDATE opportunities SET
                company=COALESCE(?, company),
                role=COALESCE(?, role),
                kind=COALESCE(?, kind),
                url=COALESCE(?, url),
                deadline_at=COALESCE(?, deadline_at),
                updated_at=?
            WHERE id=?
            """,
            (company, role, kind, url, deadline_at, _iso(), opportunity_id),
        )
        self._commit()
        out = row_to_dict(self.conn.execute("SELECT * FROM opportunities WHERE id=?", (opportunity_id,)).fetchone())
        self.set_setting("google_tracker_dirty", "1")
        self._sync_opportunity_deadline(out)
        return out

    def list_opportunities(self) -> list[dict[str, Any]]:
        return [row_to_dict(r) for r in self.conn.execute("SELECT * FROM opportunities ORDER BY updated_at DESC")]

    def get_setting(self, key: str) -> str | None:
        row = self.conn.execute("SELECT value FROM app_settings WHERE key=?", (key,)).fetchone()
        return str(row["value"]) if row else None

    def set_setting(self, key: str, value: str) -> None:
        self.conn.execute(
            """INSERT INTO app_settings(key, value, updated_at) VALUES (?, ?, ?)
               ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at""",
            (key, value, _iso()),
        )
        self._commit()

    def delete_setting(self, key: str) -> None:
        self.conn.execute("DELETE FROM app_settings WHERE key=?", (key,))
        self._commit()

    def propose(self, kind: str, payload: dict, ttl_days: int = 7) -> dict[str, Any]:
        now = _now()
        cur = self.conn.execute(
            """
            INSERT INTO pending_approvals(kind, payload, status, created_at, expires_at)
            VALUES (?, ?, 'pending', ?, ?)
            """,
            (kind, json.dumps(payload), _iso(now), _iso(now + timedelta(days=ttl_days))),
        )
        self._commit()
        return self.get_approval(int(cur.lastrowid))

    def get_approval(self, approval_id: int) -> dict[str, Any]:
        row = self.conn.execute("SELECT * FROM pending_approvals WHERE id=?", (approval_id,)).fetchone()
        if not row:
            raise ValueError("unknown approval")
        data = row_to_dict(row)
        data["payload"] = json.loads(data["payload"])
        return data

    def list_approvals(self, status: str = "pending") -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT * FROM pending_approvals WHERE status=? ORDER BY id",
            (status,),
        )
        out = []
        for row in rows:
            data = row_to_dict(row)
            try:
                data["payload"] = json.loads(data["payload"])
            except (TypeError, json.JSONDecodeError):
                data["payload"] = {"parse_error": True, "raw": data.get("payload")}
            out.append(data)
        return out

    def expire_approvals(self, now: datetime | None = None) -> int:
        now = now or _now()
        cur = self.conn.execute(
            """
            UPDATE pending_approvals SET status='expired'
            WHERE status='pending' AND expires_at <= ?
            """,
            (_iso(now),),
        )
        self._commit()
        return cur.rowcount

    def decide_approval(self, approval_id: int, accept: bool, extra: dict | None = None) -> dict[str, Any]:
        self.expire_approvals()
        row = self.conn.execute("SELECT * FROM pending_approvals WHERE id=?", (approval_id,)).fetchone()
        if not row:
            raise ValueError("unknown approval")
        if row["status"] != "pending":
            raise ValueError("approval not pending")
        payload = json.loads(row["payload"])
        if extra:
            payload.update(extra)
        if accept:
            self._apply_approval(row["kind"], payload)
            status = "accepted"
        else:
            status = "rejected"
        self.conn.execute(
            "UPDATE pending_approvals SET status=?, payload=? WHERE id=?",
            (status, json.dumps(payload), approval_id),
        )
        self._commit()
        return self.get_approval(approval_id)

    def _apply_approval(self, kind: str, payload: dict) -> None:
        if kind in {"mark_applied", "opportunity_applied"}:
            oid = payload.get("opportunity_id")
            if not oid and payload.get("url"):
                opp = self.upsert_opportunity(url=payload["url"], company=payload.get("company"), role=payload.get("role"))
                oid = opp["id"]
            if not oid:
                raise ValueError("approval missing posting — add a URL or pick a tracked opportunity first")
            self.set_opportunity_state(int(oid), "applied")
        elif kind in {"mark_skipped", "opportunity_skip"}:
            oid = payload.get("opportunity_id")
            if not oid:
                raise ValueError("approval missing opportunity")
            self.set_opportunity_state(int(oid), "skipped")
        elif kind == "keep_seen":
            oid = payload.get("opportunity_id")
            if not oid:
                raise ValueError("approval missing opportunity")
            self.set_opportunity_state(int(oid), "seen")
        elif kind == "pin_ritual":
            name = payload.get("name")
            if not name:
                raise ValueError("approval missing ritual name")
            self.add_ritual(
                name=name,
                launch_url=payload.get("launch_url"),
                match_host=payload.get("match_host"),
            )
        elif kind == "do_send":
            # Accepting still does not send or submit; the hands layer is not built.
            return

    def ingest_url(self, url: str, title: str | None = None, source: str = "url") -> dict[str, Any]:
        src = "phone" if source == "phone" else "url"
        kind = program_kind_for_url(url, title)
        if src == "phone":
            self.heartbeat("phone_aw", "browser activity received")
        else:
            self.heartbeat("mac_browser", "browser activity received")
        if not kind:
            return {"job": False, "tracked": False, "url": url}
        clean_url = canonicalize_program_url(url)
        self.add_event(src, title or clean_url, {"url": clean_url, "title": title, "kind": kind})
        opp = self.upsert_opportunity(url=clean_url, role=title, company=None, kind=kind, source="url")
        return {"job": kind == "internship", "tracked": True, "kind": kind, "opportunity": opp}

    def ingest_screen_text(self, text: str, url: str | None = None) -> dict[str, Any]:
        kind = classify_screen_text(text)
        self.add_event("screen", (text or "")[:200], {"url": url, "kind": kind})
        if not kind:
            return {"kind": None}
        if url:
            opp = self.upsert_opportunity(url=url, source="screen")
        else:
            opp = None
        if kind == "confirmation":
            if self.is_dormant():
                return {"kind": kind, "skipped": "dormant"}
            approval = self.propose(
                "mark_applied",
                {"opportunity_id": opp["id"] if opp else None, "url": url, "snippet": text[:280]},
            )
            return {"kind": kind, "approval": approval}
        if kind == "requirement_miss":
            if self.is_dormant():
                return {"kind": kind, "skipped": "dormant"}
            approval = self.propose(
                "opportunity_skip",
                {
                    "opportunity_id": opp["id"] if opp else None,
                    "url": url,
                    "snippet": text[:280],
                    "prompt": "skip (don't remind), keep as seen (reapply later), or reject to ignore",
                },
            )
            return {"kind": kind, "approval": approval}
        return {"kind": kind}

    def ingest_phone(self, summary: str, payload: dict | None = None) -> int:
        self.heartbeat("phone_a11y", summary)
        return self.add_event("phone", summary, payload)

    def add_mail_action(self, message_id: str, account: str, subject: str, classification: str, card: str) -> dict[str, Any]:
        existing = self.conn.execute("SELECT * FROM mail_actions WHERE message_id=?", (message_id,)).fetchone()
        if not existing:
            cur = self.conn.execute(
                """
                INSERT INTO mail_actions(message_id, account, subject, classification, card, status)
                VALUES (?, ?, ?, ?, ?, 'open')
                """,
                (message_id, account, subject, classification, card),
            )
            self._commit()
            row = row_to_dict(self.conn.execute("SELECT * FROM mail_actions WHERE id=?", (cur.lastrowid,)).fetchone())
        else:
            row = row_to_dict(existing)
        self._promote_mail(message_id, subject, classification, card)
        return row

    def _promote_mail(self, message_id: str, subject: str, classification: str, card: str) -> None:
        blob = f"{subject} {card}"
        url = first_url(blob) or f"mail:{message_id}"
        kind = program_kind(classification)
        if not kind and url.startswith(("http://", "https://")):
            kind = program_kind_for_url(url, blob)
        if not kind:
            guessed_kind, _ = classify_event(blob, None, None)
            kind = guessed_kind if guessed_kind in {"hackathon", "conference"} else None
        if kind and is_join_url(url):
            url = f"mail:{message_id}"
        when = parse_when(blob)
        deadline_at = _iso(when) if when and looks_like_submission(blob) else None
        if kind:
            state = "seen"
            if classification == "interview":
                state = "interview"
            elif classification == "rejection":
                state = "rejected"
            existing = self.conn.execute("SELECT * FROM opportunities WHERE url=?", (url,)).fetchone()
            if existing:
                if classification in {"interview", "rejection"}:
                    self.set_opportunity_state(existing["id"], state, kind)
                else:
                    self.upsert_opportunity(url=url, role=subject, kind=kind, deadline_at=deadline_at, source="mail")
            else:
                self.upsert_opportunity(url=url, role=subject, kind=kind, state=state, deadline_at=deadline_at, source="mail")
        if when and (kind in {"hackathon", "conference"} or classification in {"hackathon", "conference", "interview"}):
            join = pick_join_url(blob)
            end = when + timedelta(hours=2)
            self.upsert_meeting(
                uid=f"mail:{message_id}",
                title=subject,
                start_at=_iso(when),
                end_at=_iso(end),
                join_url=join,
                notes=card,
                kind="interview" if classification == "interview" else (kind or "conference"),
                modality="virtual" if join else None,
            )

    def list_mail_actions(self, status: str = "open") -> list[dict[str, Any]]:
        return [
            row_to_dict(r)
            for r in self.conn.execute("SELECT * FROM mail_actions WHERE status=? ORDER BY id DESC", (status,))
        ]

    def _resolve_join(self, title: str, join_url: str | None, location: str | None, notes: str | None) -> str | None:
        picked = pick_join_url(notes, location, preferred=join_url)
        if picked:
            return picked
        for mail in self.list_mail_actions("open"):
            if mail_matches_event(title, mail.get("subject") or ""):
                found = pick_join_url(mail.get("card"), mail.get("subject"))
                if found:
                    return found
        return None

    def upsert_meeting(
        self,
        uid: str,
        title: str,
        start_at: str,
        end_at: str,
        join_url: str | None = None,
        location: str | None = None,
        notes: str | None = None,
        kind: str | None = None,
        modality: str | None = None,
        reminder_only: bool = False,
    ) -> dict[str, Any]:
        existing = self.conn.execute("SELECT * FROM meetings WHERE uid=?", (uid,)).fetchone()
        locked = bool(existing["join_locked"]) if existing else False
        picked = self._resolve_join(title, join_url, location, notes)
        if locked:
            stored_join = existing["join_url"]
            lock_val = existing["join_locked"]
        else:
            stored_join = picked
            lock_val = existing["join_locked"] if existing else 0
        self.conn.execute(
            """
            INSERT INTO meetings(uid, title, start_at, end_at, join_url, join_locked, location, notes, reminder_only, ack, acked_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL)
            ON CONFLICT(uid) DO UPDATE SET
                title=excluded.title, start_at=excluded.start_at, end_at=excluded.end_at,
                join_url=excluded.join_url, join_locked=excluded.join_locked,
                location=excluded.location, notes=excluded.notes, reminder_only=excluded.reminder_only
            """,
            (uid, title, start_at, end_at, stored_join, lock_val, location, notes, int(reminder_only)),
        )
        self._commit()
        row = row_to_dict(self.conn.execute("SELECT * FROM meetings WHERE uid=?", (uid,)).fetchone())
        if not row.get("confirmed"):
            guess_kind, guess_mod = classify_event(title, stored_join, location, notes)
            kind = kind or guess_kind
            modality = modality or guess_mod
            reminder_only = reminder_only or kind in {"deadline", "calendar_note"}
            self.conn.execute("UPDATE meetings SET kind=?, modality=?, reminder_only=? WHERE uid=?", (kind, modality, int(reminder_only), uid))
            self._commit()
        self.sync_reminders(uid)
        out = row_to_dict(self.conn.execute("SELECT * FROM meetings WHERE uid=?", (uid,)).fetchone())
        if not reminder_only and out.get("kind") in {"hackathon", "conference"}:
            program_url = None
            for match in URL_RE.finditer(" ".join(x for x in (notes, location) if x)):
                candidate = match.group(0).rstrip(").,")
                if not is_join_url(candidate):
                    program_url = candidate
                    break
            self.upsert_opportunity(
                url=program_url or (uid if uid.startswith("mail:") else f"calendar:{uid}"),
                role=title,
                kind=out["kind"],
                source="calendar" if not uid.startswith("mail:") else "mail",
            )
        return out

    def patch_meeting(
        self,
        meeting_id: int,
        *,
        join_url: str | None = None,
        modality: str | None = None,
        kind: str | None = None,
        title: str | None = None,
    ) -> dict[str, Any]:
        row = self.conn.execute("SELECT * FROM meetings WHERE id=?", (meeting_id,)).fetchone()
        if not row:
            raise ValueError("unknown meeting")
        if title is not None:
            self.conn.execute("UPDATE meetings SET title=? WHERE id=?", (title, meeting_id))
        if kind is not None:
            self.conn.execute("UPDATE meetings SET kind=? WHERE id=?", (kind, meeting_id))
        if modality is not None:
            self.conn.execute("UPDATE meetings SET modality=? WHERE id=?", (modality, meeting_id))
        if join_url is not None:
            self.conn.execute(
                "UPDATE meetings SET join_url=?, join_locked=1 WHERE id=?",
                (join_url, meeting_id),
            )
        self._commit()
        uid = row["uid"]
        self.sync_reminders(uid)
        return row_to_dict(self.conn.execute("SELECT * FROM meetings WHERE id=?", (meeting_id,)).fetchone())

    def sync_reminders(self, uid: str) -> None:
        row = self.conn.execute("SELECT * FROM meetings WHERE uid=?", (uid,)).fetchone()
        if not row:
            return
        start = datetime.fromisoformat(row["start_at"].replace("Z", "+00:00"))
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        kind = row["kind"] or "meeting"
        modality = row["modality"] or "virtual"
        title = row["title"] or ""
        notes = row["notes"] or ""
        submit = start if looks_like_submission(title, notes) else None
        present = start if looks_like_presentation(title, notes) else None
        if submit and kind == "hackathon" and looks_like_submission(title, notes):
            fires = [("submit_4h", start - timedelta(hours=4))]
        elif present and looks_like_presentation(title, notes) and not looks_like_submission(title, notes):
            fires = [("present_30m", start - timedelta(minutes=30))]
        else:
            fires = reminder_fires(kind, modality, start, submit=submit, present=present, now=_now())
        purposes = [purpose for purpose, _ in fires]
        if purposes:
            placeholders = ",".join("?" for _ in purposes)
            self.conn.execute(
                f"DELETE FROM reminders WHERE event_uid=? AND acked_at IS NULL AND purpose NOT IN ({placeholders})",
                (uid, *purposes),
            )
        else:
            self.conn.execute("DELETE FROM reminders WHERE event_uid=? AND acked_at IS NULL", (uid,))
        for purpose, due in fires:
            self.conn.execute(
                """
                INSERT INTO reminders(event_uid, purpose, due_at, acked_at)
                VALUES (?, ?, ?, NULL)
                ON CONFLICT(event_uid, purpose) DO UPDATE SET due_at=excluded.due_at
                WHERE reminders.acked_at IS NULL
                """,
                (uid, purpose, _iso(due.astimezone(timezone.utc))),
            )
        self._maybe_auto_interview_quiet(row_to_dict(row))
        self._commit()

    def _maybe_auto_interview_quiet(self, meeting: dict[str, Any]) -> None:
        kind = (meeting.get("kind") or "").lower()
        title = meeting.get("title") or ""
        if kind != "interview" and not re.search(r"\binterview\b", title, re.I):
            return
        start = parse_iso(meeting["start_at"])
        end = parse_iso(meeting["end_at"])
        now = _now()
        if start.astimezone(timezone.utc) < now - timedelta(hours=1):
            return
        self.ensure_auto_quiet(
            meeting_id=int(meeting["id"]),
            level="quiet",
            starts_at=quiet_iso(start - timedelta(minutes=5)),
            ends_at=quiet_iso(end + timedelta(minutes=5)),
            reason=f"Interview: {title[:80]}",
            source="auto_interview",
        )

    def ensure_auto_quiet(
        self,
        *,
        meeting_id: int,
        level: str,
        starts_at: str,
        ends_at: str,
        reason: str,
        source: str,
    ) -> dict[str, Any] | None:
        existing = self.conn.execute(
            "SELECT * FROM quiet_periods WHERE meeting_id=? AND source=? LIMIT 1",
            (meeting_id, source),
        ).fetchone()
        if existing:
            return row_to_dict(existing)
        return self.create_quiet(
            level=level,
            starts_at=starts_at,
            ends_at=ends_at,
            reason=reason,
            source=source,
            meeting_id=meeting_id,
        )

    def create_quiet(
        self,
        *,
        level: str,
        starts_at: str | None = None,
        ends_at: str | None = None,
        minutes: int | None = None,
        reason: str | None = None,
        source: str = "manual",
        meeting_id: int | None = None,
        goal_id: int | None = None,
    ) -> dict[str, Any]:
        if level not in QUIET_LEVELS:
            raise ValueError("level must be mild, quiet, or dormant")
        now = _now()
        start_s = starts_at or _iso(now)
        if ends_at:
            end_s = ends_at
        elif minutes is not None:
            end_s = end_from_minutes(minutes, now)
        else:
            end_s = end_from_minutes(60, now)
        if parse_iso(end_s) <= parse_iso(start_s):
            raise ValueError("ends_at must be after starts_at")
        cur = self.conn.execute(
            """
            INSERT INTO quiet_periods(level, starts_at, ends_at, reason, source, meeting_id, goal_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (level, start_s, end_s, reason, source, meeting_id, goal_id),
        )
        self._commit()
        return row_to_dict(self.conn.execute("SELECT * FROM quiet_periods WHERE id=?", (cur.lastrowid,)).fetchone())

    def end_quiet(self, quiet_id: int) -> dict[str, Any]:
        row = self.conn.execute("SELECT * FROM quiet_periods WHERE id=?", (quiet_id,)).fetchone()
        if not row:
            raise ValueError("unknown quiet period")
        now_s = _iso()
        self.conn.execute("UPDATE quiet_periods SET ends_at=? WHERE id=?", (now_s, quiet_id))
        self._commit()
        return row_to_dict(self.conn.execute("SELECT * FROM quiet_periods WHERE id=?", (quiet_id,)).fetchone())

    def panic_quiet(self) -> dict[str, Any]:
        return self.create_quiet(level="dormant", minutes=PANIC_MINUTES, reason="panic", source="manual")

    def list_quiet(self, now: datetime | None = None) -> list[dict[str, Any]]:
        now_s = _iso(now or _now())
        rows = self.conn.execute(
            """
            SELECT * FROM quiet_periods
            WHERE ends_at > ?
            ORDER BY starts_at
            """,
            (now_s,),
        )
        return [row_to_dict(r) for r in rows]

    def active_quiet(self, now: datetime | None = None) -> dict[str, Any] | None:
        now_dt = now or _now()
        now_s = _iso(now_dt)
        row = self.conn.execute(
            """
            SELECT * FROM quiet_periods
            WHERE starts_at <= ? AND ends_at > ?
            ORDER BY CASE level WHEN 'dormant' THEN 0 WHEN 'quiet' THEN 1 ELSE 2 END
            LIMIT 1
            """,
            (now_s, now_s),
        ).fetchone()
        return quiet_public(row_to_dict(row), now_dt) if row else None

    def is_dormant(self, now: datetime | None = None) -> bool:
        q = self.active_quiet(now)
        return bool(q and q.get("level") == "dormant")

    def quiet_summary(self, now: datetime | None = None) -> dict[str, Any] | None:
        return self.active_quiet(now)

    def _meeting_join_url(self, data: dict[str, Any]) -> str | None:
        return pick_join_url(data.get("join_url"), data.get("notes"), data.get("location"))

    def _sanitize_halt(self, data: dict[str, Any]) -> dict[str, Any]:
        if not data:
            return data
        cleaned = pick_join_url(data.get("join_url"), data.get("notes"), data.get("location"))
        if cleaned:
            data["join_url"] = cleaned
        return data

    def _meeting_for_halt(self, data: dict[str, Any]) -> dict[str, Any]:
        if data.get("halt_kind") == "reminder":
            mid = data.get("meeting_id")
            if mid:
                row = self.conn.execute("SELECT * FROM meetings WHERE id=?", (mid,)).fetchone()
                if row:
                    return row_to_dict(row)
        if data.get("id") and not data.get("halt_kind"):
            row = self.conn.execute("SELECT * FROM meetings WHERE id=?", (data["id"],)).fetchone()
            if row:
                return row_to_dict(row)
        return data

    def _enrich_halt(self, data: dict[str, Any] | None) -> dict[str, Any] | None:
        if not data:
            return data
        out = self._sanitize_halt(dict(data))
        meeting = self._meeting_for_halt(out)
        join_url = self._meeting_join_url(meeting) or out.get("join_url")
        modality = (meeting.get("modality") or out.get("modality") or "virtual").lower()
        physical = modality == "physical"
        reminder = out.get("halt_kind") == "reminder"
        purpose = out.get("purpose")
        early_reminder = reminder and purpose in EARLY_REMINDER_PURPOSES
        out["early_reminder"] = early_reminder
        out["requires_join"] = bool(join_url) and not physical and not early_reminder
        out["can_open_link"] = bool(join_url) and early_reminder
        out["can_im_in"] = not reminder and not out["requires_join"]
        out["can_headed"] = reminder and physical and out.get("purpose") == "start_2h"
        if out["requires_join"]:
            out["im_in_hint"] = "Join opens the meeting link. I'm in is disabled for virtual calls."
        elif physical:
            out["im_in_hint"] = "Tap twice to confirm you are on site."
        else:
            out["im_in_hint"] = "Tap twice to confirm you are on the call."
        return out

    def join_meeting(self, meeting_id: int, reminder_id: int | None = None) -> dict[str, Any]:
        row = self.conn.execute("SELECT * FROM meetings WHERE id=?", (meeting_id,)).fetchone()
        if not row:
            raise ValueError("unknown meeting")
        data = row_to_dict(row)
        url = self._meeting_join_url(data)
        if not url:
            raise ValueError("no join link for this meeting")
        purpose = None
        if reminder_id is not None:
            rem = self.conn.execute("SELECT purpose FROM reminders WHERE id=?", (reminder_id,)).fetchone()
            if rem:
                purpose = rem["purpose"]
        early = purpose in EARLY_REMINDER_PURPOSES
        from timeless.hands import run as run_hands

        run_hands({"action": "open_url", "target": "mac", "url": url})
        try:
            run_hands({"action": "open_url", "target": "phone", "url": url})
        except Exception:
            pass
        if early:
            if reminder_id is not None:
                self.conn.execute(
                    "UPDATE reminders SET acked_at=? WHERE id=? AND acked_at IS NULL",
                    (_iso(), reminder_id),
                )
                self._commit()
            return {"ok": True, "url": url, "meeting": data, "early": True}
        out = self.ack_meeting(meeting_id, "join")
        if reminder_id is not None:
            self.conn.execute(
                "UPDATE reminders SET acked_at=? WHERE id=? AND acked_at IS NULL",
                (_iso(), reminder_id),
            )
            self._commit()
        return {"ok": True, "url": url, "meeting": out}

    def due_reminder(self, now: datetime | None = None) -> dict[str, Any] | None:
        now_dt = now or _now()
        now_s = _iso(now_dt)
        floor = _iso(now_dt - timedelta(hours=18))
        soon = _iso(now_dt + timedelta(hours=24))
        row = self.conn.execute(
            """
            SELECT r.id, r.purpose, r.due_at, r.event_uid, m.id AS meeting_id, m.title, m.join_url,
                   m.kind, m.modality, m.confirmed, m.start_at, m.end_at, m.location
            FROM reminders r
            JOIN meetings m ON m.uid = r.event_uid
            WHERE r.acked_at IS NULL AND r.due_at <= ? AND r.due_at >= ? AND m.end_at > ?
              AND NOT (r.purpose LIKE 'start_%' AND m.start_at <= ?)
              AND NOT (r.purpose = 'start_1d' AND m.start_at <= ?)
            ORDER BY r.due_at LIMIT 1
            """,
            (now_s, floor, now_s, now_s, soon),
        ).fetchone()
        if not row:
            return None
        data = row_to_dict(row)
        data["halt_kind"] = "reminder"
        return self._enrich_halt(data)

    def ack_reminder(self, reminder_id: int, action: str, kind: str | None = None, modality: str | None = None) -> dict[str, Any]:
        row = self.conn.execute("SELECT * FROM reminders WHERE id=?", (reminder_id,)).fetchone()
        if not row:
            raise ValueError("unknown reminder")
        if action not in {"confirm", "change", "headed", "dismiss", "im_in"}:
            raise ValueError("unsupported reminder action")
        if action == "headed":
            meeting = self.conn.execute("SELECT modality FROM meetings WHERE uid=?", (row["event_uid"],)).fetchone()
            if row["purpose"] != "start_2h" or not meeting or meeting["modality"] != "physical":
                raise ValueError("headed is only available for the two-hour physical reminder")
        if action in {"confirm", "change"}:
            self.conn.execute(
                "UPDATE meetings SET kind=COALESCE(?, kind), modality=COALESCE(?, modality), confirmed=1 WHERE uid=?",
                (kind, modality, row["event_uid"]),
            )
            self.conn.execute("UPDATE reminders SET acked_at=? WHERE id=? AND acked_at IS NULL", (_iso(), reminder_id))
            self.sync_reminders(row["event_uid"])
            self._commit()
            return self.due_reminder() or row_to_dict(row)
        self.conn.execute("UPDATE reminders SET acked_at=? WHERE id=?", (_iso(), reminder_id))
        self._commit()
        return row_to_dict(self.conn.execute("SELECT * FROM reminders WHERE id=?", (reminder_id,)).fetchone())

    def ack_meeting(self, meeting_id: int, action: str, *, confirm: bool = False) -> dict[str, Any]:
        if action not in MEETING_ACKS:
            raise ValueError("action must be join or im_in")
        row = self.conn.execute("SELECT * FROM meetings WHERE id=?", (meeting_id,)).fetchone()
        if not row:
            raise ValueError("unknown meeting")
        data = row_to_dict(row)
        if action == "im_in":
            start = parse_iso(data["start_at"])
            if _now() < start.astimezone(timezone.utc) - timedelta(minutes=15):
                raise ValueError("check-in opens 15 minutes before the event")
            join_url = self._meeting_join_url(data)
            virtual = (data.get("modality") or "virtual").lower() != "physical"
            if join_url and virtual:
                raise ValueError("use Join for virtual meetings with a link")
            if not confirm:
                raise ValueError("confirm check-in required")
        self.conn.execute(
            "UPDATE meetings SET ack=?, acked_at=? WHERE id=?",
            (action, _iso(), meeting_id),
        )
        self._commit()
        return row_to_dict(self.conn.execute("SELECT * FROM meetings WHERE id=?", (meeting_id,)).fetchone())

    def close_elapsed_meetings(self, now: datetime | None = None) -> int:
        now_s = _iso(now or _now())
        cur = self.conn.execute(
            """
            UPDATE meetings SET ack='missed'
            WHERE ack IS NULL AND end_at <= ?
            """,
            (now_s,),
        )
        self._commit()
        return cur.rowcount

    def _raw_active_halt(self, now: datetime | None = None) -> dict[str, Any] | None:
        due = self.due_reminder(now)
        if due:
            return due
        now_s = _iso(now or _now())
        row = self.conn.execute(
            """
            SELECT * FROM meetings
            WHERE ack IS NULL AND reminder_only=0 AND start_at <= ? AND end_at > ?
            ORDER BY start_at LIMIT 1
            """,
            (now_s, now_s),
        ).fetchone()
        if not row:
            return None
        return self._enrich_halt(row_to_dict(row))

    def active_halt(self, now: datetime | None = None) -> dict[str, Any] | None:
        self.close_elapsed_meetings(now)
        raw = self._raw_active_halt(now)
        if not raw:
            return None
        quiet = self.active_quiet(now)
        if quiet and blocks_halt(quiet["level"]):
            title = raw.get("title") or "halt"
            self.heartbeat("quiet_mute", f"{quiet['level']}:{title}")
            return None
        if quiet and quiet["level"] == "mild":
            out = dict(raw)
            out["presentation"] = "banner"
            return out
        return raw

    def list_meetings(self) -> list[dict[str, Any]]:
        return [row_to_dict(r) for r in self.conn.execute("SELECT * FROM meetings WHERE reminder_only=0 ORDER BY start_at")]

    def needs_gate(self, day: str | None = None) -> bool:
        return self.get_plan(day) is None

    def get_reflection(self, day: str | None = None) -> dict[str, Any]:
        day = day or _day()
        row = self.conn.execute("SELECT * FROM daily_reflections WHERE day=?", (day,)).fetchone()
        return row_to_dict(row) if row else {"day": day, "lesson": None}

    def save_reflection(self, day: str, lesson: str | None) -> dict[str, Any]:
        """One sentence about the day. Empty clears it."""
        day = day or _day()
        text = (lesson or "").strip()[:600] or None
        now = _iso()
        self.conn.execute(
            """
            INSERT INTO daily_reflections(day, lesson, created_at, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(day) DO UPDATE SET lesson=excluded.lesson, updated_at=excluded.updated_at
            """,
            (day, text, now, now),
        )
        self._commit()
        return self.get_reflection(day)

    def correct_activity(self, day: str, title: str, bucket: str) -> dict[str, Any]:
        """Override how one observed item was bucketed.

        The classifier is a keyword guess; when it is wrong the owner's ruling
        replaces it, for this day's estimate and for the recap that reads it.
        """
        if bucket not in ACTIVITY_BUCKETS:
            raise ValueError(f"bucket must be one of {', '.join(sorted(ACTIVITY_BUCKETS))}")
        title = (title or "").strip()
        if not title:
            raise ValueError("title required")
        self.conn.execute(
            """
            INSERT INTO activity_corrections(day, title, bucket, created_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(day, title) DO UPDATE SET bucket=excluded.bucket, created_at=excluded.created_at
            """,
            (day, title[:240], bucket, _iso()),
        )
        self._commit()
        self.add_event("correction", f"{title[:60]} -> {bucket}", {"day": day, "bucket": bucket})
        return {"day": day, "title": title[:240], "bucket": bucket}

    def activity_corrections(self, day: str) -> dict[str, str]:
        return {
            row["title"]: row["bucket"]
            for row in self.conn.execute("SELECT title, bucket FROM activity_corrections WHERE day=?", (day,))
        }

    def get_recap(self, day: str) -> dict[str, Any] | None:
        row = self.conn.execute("SELECT * FROM daily_recaps WHERE day=?", (day,)).fetchone()
        if not row:
            return None
        data = row_to_dict(row)
        data["cards"] = json.loads(data["cards"])
        data["phone_synced"] = bool(data["phone_synced"])
        return data

    def save_recap(self, day: str, cards: list[dict], phone_synced: bool) -> dict[str, Any]:
        payload = json.dumps(cards)
        now = _iso()
        self.conn.execute(
            """
            INSERT INTO daily_recaps(day, cards, phone_synced, generated_at, acked_at)
            VALUES (?, ?, ?, ?, NULL)
            ON CONFLICT(day) DO UPDATE SET
              cards=excluded.cards,
              phone_synced=excluded.phone_synced,
              generated_at=excluded.generated_at
            WHERE daily_recaps.acked_at IS NULL
            """,
            (day, payload, 1 if phone_synced else 0, now),
        )
        self._commit()
        row = self.get_recap(day)
        if row is None:
            raise ValueError("recap missing")
        return row

    def unjudged_goals(self, day: str) -> list[dict[str, Any]]:
        """Goals the owner never gave an outcome. The one thing that blocks a close."""
        return [g for g in self.list_goals(day) if (g.get("status") or "planned") in {"planned", "active"}]

    def ack_recap(self, day: str | None = None, now: datetime | None = None) -> dict[str, Any]:
        day = day or due_recap_day(now)
        row = self.get_recap(day)
        if not row:
            raise ValueError("unknown recap")
        if row.get("acked_at"):
            return row
        # Enforced here, not in the interface: a disabled button is a courtesy to
        # one client, while the day's record has to be unambiguous for every client.
        pending = self.unjudged_goals(day)
        if pending:
            names = ", ".join(g["text"] for g in pending[:3])
            more = f" and {len(pending) - 3} more" if len(pending) > 3 else ""
            plural = len(pending) != 1
            raise ValueError(
                f"{len(pending)} goal{'s' if plural else ''} still "
                f"{'need' if plural else 'needs'} an outcome: {names}{more}"
            )
        self.conn.execute("UPDATE daily_recaps SET acked_at=? WHERE day=?", (_iso(now), day))
        self._commit()
        recap = self.get_recap(day)
        if recap is None:
            raise ValueError("unknown recap")
        return recap

    def needs_recap(self, now: datetime | None = None) -> bool:
        day = due_recap_day(now)
        row = self.get_recap(day)
        return row is None or not row.get("acked_at")

    def events_on_day(self, day: str) -> list[dict[str, Any]]:
        out = []
        for r in self.conn.execute("SELECT * FROM events ORDER BY ts"):
            data = row_to_dict(r)
            ts = datetime.strptime(data["ts"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            if day_key(ts) != day:
                continue
            if data.get("payload"):
                data["payload"] = json.loads(data["payload"])
            out.append(data)
        return out

    def heatmap(self, weeks: int = 53) -> list[dict[str, Any]]:
        counts: dict[str, int] = {}
        for r in self.conn.execute("SELECT ts FROM events"):
            try:
                ts = datetime.strptime(r["ts"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            except (TypeError, ValueError):
                continue
            key = day_key(ts)
            counts[key] = counts.get(key, 0) + 1
        loc = datetime.strptime(day_key(), "%Y-%m-%d")
        start = loc - timedelta(days=weeks * 7 - 1)
        days = []
        cur = start
        while cur <= loc:
            key = cur.strftime("%Y-%m-%d")
            days.append({"day": key, "count": counts.get(key, 0)})
            cur += timedelta(days=1)
        return days


def _serialized(method):
    @wraps(method)
    def guarded(self, *args, **kwargs):
        with self._lock:
            if self._poisoned and method.__name__ not in _POISON_SAFE:
                raise StoreUnavailable(
                    "the database connection failed mid-transaction and was discarded; reconnect to continue"
                )
            return method(self, *args, **kwargs)

    return guarded


# Store methods often call one another, so this deliberately uses an RLock.
# Wrapping at the class boundary keeps multi-statement reads and writes atomic
# without scattering lock bookkeeping across every query method.
for _method_name, _method in list(vars(Store).items()):
    if _method_name != "__init__" and callable(_method) and not _method_name.startswith("__"):
        setattr(Store, _method_name, _serialized(_method))
