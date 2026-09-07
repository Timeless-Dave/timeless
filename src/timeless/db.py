from __future__ import annotations

import re
import sqlite3
from pathlib import Path

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS opportunities (
    id INTEGER PRIMARY KEY,
    company TEXT,
    role TEXT,
    url TEXT,
    state TEXT NOT NULL CHECK (state IN ('seen','applied','shortlisted','interview','waiting','offer','rejected','skipped','ignored')),
    kind TEXT NOT NULL DEFAULT 'internship',
    deadline_at TEXT,
    source TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS pending_approvals (
    id INTEGER PRIMARY KEY,
    kind TEXT NOT NULL,
    payload TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('pending','accepted','rejected','expired')),
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS daily_plans (
    id INTEGER PRIMARY KEY,
    day TEXT NOT NULL UNIQUE,
    outcomes TEXT NOT NULL,
    timeline TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS plan_goals (
    id INTEGER PRIMARY KEY,
    day TEXT NOT NULL,
    text TEXT NOT NULL,
    position INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'planned' CHECK (status IN ('planned','active','done','partial','deferred','dropped')),
    note TEXT,
    carried_from INTEGER,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    completed_at TEXT,
    archived_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_plan_goals_day ON plan_goals(day, position);

CREATE TABLE IF NOT EXISTS rituals (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    launch_url TEXT,
    app_bundle TEXT,
    weekdays TEXT,
    match_host TEXT,
    min_minutes INTEGER
);

CREATE TABLE IF NOT EXISTS ritual_completions (
    id INTEGER PRIMARY KEY,
    ritual_id INTEGER NOT NULL,
    day TEXT NOT NULL,
    praise TEXT,
    created_at TEXT NOT NULL,
    UNIQUE (ritual_id, day),
    FOREIGN KEY (ritual_id) REFERENCES rituals(id)
);

CREATE TABLE IF NOT EXISTS meetings (
    id INTEGER PRIMARY KEY,
    uid TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    start_at TEXT NOT NULL,
    end_at TEXT NOT NULL,
    join_url TEXT,
    join_locked INTEGER NOT NULL DEFAULT 0,
    location TEXT,
    notes TEXT,
    kind TEXT,
    modality TEXT,
    confirmed INTEGER NOT NULL DEFAULT 0,
    reminder_only INTEGER NOT NULL DEFAULT 0,
    ack TEXT CHECK (ack IN ('join','im_in','missed') OR ack IS NULL),
    acked_at TEXT
);

CREATE TABLE IF NOT EXISTS reminders (
    id INTEGER PRIMARY KEY,
    event_uid TEXT NOT NULL,
    purpose TEXT NOT NULL,
    due_at TEXT NOT NULL,
    acked_at TEXT,
    UNIQUE (event_uid, purpose)
);

CREATE TABLE IF NOT EXISTS mail_actions (
    id INTEGER PRIMARY KEY,
    message_id TEXT NOT NULL UNIQUE,
    account TEXT NOT NULL,
    subject TEXT,
    classification TEXT NOT NULL,
    card TEXT,
    status TEXT NOT NULL DEFAULT 'open'
);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY,
    source TEXT NOT NULL,
    ts TEXT NOT NULL,
    summary TEXT,
    payload TEXT
);

CREATE TABLE IF NOT EXISTS heartbeats (
    sensor TEXT PRIMARY KEY,
    last_seen TEXT NOT NULL,
    detail TEXT
);

CREATE TABLE IF NOT EXISTS daily_recaps (
    day TEXT PRIMARY KEY,
    cards TEXT NOT NULL,
    phone_synced INTEGER NOT NULL DEFAULT 0,
    generated_at TEXT NOT NULL,
    acked_at TEXT
);

CREATE TABLE IF NOT EXISTS daily_reflections (
    day TEXT PRIMARY KEY,
    lesson TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS activity_corrections (
    id INTEGER PRIMARY KEY,
    day TEXT NOT NULL,
    title TEXT NOT NULL,
    bucket TEXT NOT NULL CHECK (bucket IN ('aligned','productive_off_plan','distracting','unknown')),
    created_at TEXT NOT NULL,
    UNIQUE (day, title)
);

CREATE TABLE IF NOT EXISTS quiet_periods (
    id INTEGER PRIMARY KEY,
    level TEXT NOT NULL CHECK (level IN ('mild','quiet','dormant')),
    starts_at TEXT NOT NULL,
    ends_at TEXT NOT NULL,
    reason TEXT,
    source TEXT NOT NULL,
    meeting_id INTEGER,
    goal_id INTEGER
);

CREATE TABLE IF NOT EXISTS block_runs (
    id INTEGER PRIMARY KEY,
    day TEXT NOT NULL,
    block_id TEXT NOT NULL,
    goal_id INTEGER,
    state TEXT NOT NULL CHECK (state IN ('running','paused','done')),
    started_at TEXT NOT NULL,
    ended_at TEXT,
    accumulated_seconds REAL NOT NULL DEFAULT 0,
    resumed_at TEXT,
    updated_at TEXT NOT NULL,
    UNIQUE (day, block_id)
);

CREATE TABLE IF NOT EXISTS app_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS activity_samples (
    id INTEGER PRIMARY KEY,
    source TEXT NOT NULL,
    source_id TEXT NOT NULL,
    ts TEXT NOT NULL,
    duration_seconds REAL NOT NULL DEFAULT 0,
    app TEXT,
    host TEXT,
    title TEXT,
    category TEXT NOT NULL,
    productivity TEXT NOT NULL CHECK (productivity IN ('productive','distracting','neutral')),
    UNIQUE(source, source_id)
);
CREATE INDEX IF NOT EXISTS idx_activity_samples_ts ON activity_samples(ts);
"""

def connect(path: str | Path) -> sqlite3.Connection:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    migrate(conn)
    conn.commit()
    return conn


def migrate(conn: sqlite3.Connection) -> None:
    opp_sql = conn.execute("SELECT sql FROM sqlite_master WHERE name='opportunities'").fetchone()
    if opp_sql and "shortlisted" not in (opp_sql["sql"] or ""):
        conn.executescript(
            """
            CREATE TABLE opportunities_mig (
                id INTEGER PRIMARY KEY,
                company TEXT,
                role TEXT,
                url TEXT,
                state TEXT NOT NULL CHECK (state IN ('seen','applied','shortlisted','interview','waiting','offer','rejected','skipped','ignored')),
                kind TEXT NOT NULL DEFAULT 'internship',
                deadline_at TEXT,
                source TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            INSERT INTO opportunities_mig(id, company, role, url, state, kind, deadline_at, source, created_at, updated_at)
            SELECT id, company, role, url, state, 'internship', deadline_at, source, created_at, updated_at FROM opportunities;
            DROP TABLE opportunities;
            ALTER TABLE opportunities_mig RENAME TO opportunities;
            """
        )
    cols = {row[1] for row in conn.execute("PRAGMA table_info(meetings)")}
    for name, ddl in (
        ("location", "ALTER TABLE meetings ADD COLUMN location TEXT"),
        ("notes", "ALTER TABLE meetings ADD COLUMN notes TEXT"),
        ("kind", "ALTER TABLE meetings ADD COLUMN kind TEXT"),
        ("modality", "ALTER TABLE meetings ADD COLUMN modality TEXT"),
        ("confirmed", "ALTER TABLE meetings ADD COLUMN confirmed INTEGER NOT NULL DEFAULT 0"),
        ("reminder_only", "ALTER TABLE meetings ADD COLUMN reminder_only INTEGER NOT NULL DEFAULT 0"),
        ("join_locked", "ALTER TABLE meetings ADD COLUMN join_locked INTEGER NOT NULL DEFAULT 0"),
    ):
        if name not in cols:
            conn.execute(ddl)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS reminders (
            id INTEGER PRIMARY KEY,
            event_uid TEXT NOT NULL,
            purpose TEXT NOT NULL,
            due_at TEXT NOT NULL,
            acked_at TEXT,
            UNIQUE (event_uid, purpose)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS quiet_periods (
            id INTEGER PRIMARY KEY,
            level TEXT NOT NULL CHECK (level IN ('mild','quiet','dormant')),
            starts_at TEXT NOT NULL,
            ends_at TEXT NOT NULL,
            reason TEXT,
            source TEXT NOT NULL,
            meeting_id INTEGER
        )
        """
    )
    goal_cols = {row[1] for row in conn.execute("PRAGMA table_info(plan_goals)")}
    if "archived_at" not in goal_cols:
        conn.execute("ALTER TABLE plan_goals ADD COLUMN archived_at TEXT")
    quiet_cols = {row[1] for row in conn.execute("PRAGMA table_info(quiet_periods)")}
    if "goal_id" not in quiet_cols:
        conn.execute("ALTER TABLE quiet_periods ADD COLUMN goal_id INTEGER")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS block_runs (
            id INTEGER PRIMARY KEY,
            day TEXT NOT NULL,
            block_id TEXT NOT NULL,
            goal_id INTEGER,
            state TEXT NOT NULL CHECK (state IN ('running','paused','done')),
            started_at TEXT NOT NULL,
            ended_at TEXT,
            accumulated_seconds REAL NOT NULL DEFAULT 0,
            resumed_at TEXT,
            updated_at TEXT NOT NULL,
            UNIQUE (day, block_id)
        )
        """
    )
    _backfill_plan_goals(conn)


def _backfill_plan_goals(conn: sqlite3.Connection) -> None:
    """Give every stored plan real goal rows.

    Goals used to live only as the newline-joined ``daily_plans.outcomes`` blob,
    so days planned before this table existed have no rows to carry status on.
    """
    planned_days = {row["day"] for row in conn.execute("SELECT DISTINCT day FROM plan_goals")}
    plans = conn.execute("SELECT day, outcomes, created_at, updated_at FROM daily_plans").fetchall()
    for row in plans:
        if row["day"] in planned_days:
            continue
        position = 0
        for line in re.split(r"[\n;]+", row["outcomes"] or ""):
            text = re.sub(r"^\s*(?:[-•]|\d+[.)])\s*", "", line).strip()
            if not text:
                continue
            conn.execute(
                """
                INSERT INTO plan_goals(day, text, position, status, created_at, updated_at)
                VALUES (?, ?, ?, 'planned', ?, ?)
                """,
                (row["day"], text, position, row["created_at"], row["updated_at"]),
            )
            position += 1
