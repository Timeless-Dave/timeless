from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from timeless.app import create_app
from timeless.clock import zone
from timeless.store import Store, StoreUnavailable


@pytest.fixture
def store(tmp_path):
    return Store(str(tmp_path / "work.db"))


def block(start="09:00", end="10:00", task="work", **extra):
    return {"start": start, "end": end, "task": task, **extra}


@pytest.fixture
def clock(monkeypatch):
    """Pin the store's clock to local noon.

    `active_work` reads the wall clock to decide which block covers "now", so
    these tests build windows hours either side of it. Anchored to the real time
    of day, an offset of a couple of hours wraps past midnight after about
    21:00 — a block becomes 23:30 to 00:30, sorts before everything else, and
    the suite starts failing in the evening. Noon cannot wrap.
    """
    base = datetime.now(zone()).replace(hour=12, minute=0, second=0, microsecond=0)
    monkeypatch.setattr("timeless.store._now", lambda: base.astimezone(timezone.utc))
    return base


def window(clock, offset_minutes=0, length=60):
    """A block window relative to the frozen clock."""
    start = clock + timedelta(minutes=offset_minutes)
    end = start + timedelta(minutes=length)
    assert start.date() == end.date() == clock.date(), "a test window must not cross midnight"
    return start.strftime("%H:%M"), end.strftime("%H:%M")


# --- block identity -----------------------------------------------------


def test_an_edit_that_omits_block_id_keeps_the_run_history(store):
    """The bug: the editor dropped block_id, so every save orphaned recorded work."""
    plan = store.save_plan("Ship it", [block()], day="2026-09-06")
    original = plan["timeline"][0]["block_id"]
    store.start_block("2026-09-06", original)
    store.finish_block("2026-09-06", original)

    # A client that does not echo the id back must not lose the run.
    resaved = store.save_plan("Ship it", [block()], day="2026-09-06")
    assert resaved["timeline"][0]["block_id"] == original
    assert store.block_run("2026-09-06", original)["state"] == "done"
    assert len(store.block_runs("2026-09-06")) == 1, "no orphaned runs"


def test_an_echoed_block_id_always_wins(store):
    plan = store.save_plan("A", [block()], day="2026-09-06")
    original = plan["timeline"][0]["block_id"]
    moved = store.save_plan("A", [block("14:00", "15:00", "renamed", block_id=original)], day="2026-09-06")
    assert moved["timeline"][0]["block_id"] == original


def test_identity_is_not_inherited_when_the_match_is_ambiguous(store):
    plan = store.save_plan("A", [block(task="same"), block("11:00", "12:00", "same")], day="2026-09-06")
    first = plan["timeline"][0]["block_id"]
    # Same task at a different time is still a single exact match, so it inherits.
    again = store.save_plan("A", [block(task="same")], day="2026-09-06")
    assert again["timeline"][0]["block_id"] == first

    # Two blocks can only share a full signature when their times are the loose
    # legacy kind, since identical HH:MM windows would be rejected as overlapping.
    store.save_plan("A", [block("9", "10", "dup"), block("9", "10", "dup")], day="2026-09-07")
    stored = {b["block_id"] for b in store.get_plan("2026-09-07")["timeline"]}
    reduced = store.save_plan("A", [block("9", "10", "dup")], day="2026-09-07")
    assert reduced["timeline"][0]["block_id"] not in stored, "a fresh id is minted rather than guessed"


def test_a_changed_block_does_not_steal_another_blocks_identity(store):
    plan = store.save_plan("A", [block(task="one"), block("11:00", "12:00", "two")], day="2026-09-06")
    ids = [b["block_id"] for b in plan["timeline"]]
    swapped = store.save_plan("A", [block("11:00", "12:00", "two"), block(task="one")], day="2026-09-06")
    assert [b["block_id"] for b in swapped["timeline"]] == [ids[1], ids[0]], "identity follows content"


# --- goal-only plans ----------------------------------------------------


def test_a_goal_only_day_is_accepted(store):
    plan = store.save_plan("Read the paper", [], day="2026-09-06")
    assert plan["timeline"] == []
    assert [g["text"] for g in plan["goals"]] == ["Read the paper"]


def test_the_api_accepts_a_goal_only_day(tmp_path):
    client = TestClient(create_app(str(tmp_path / "api.db")))
    response = client.post("/api/plan", json={"goals": [{"text": "Read the paper"}], "day": "2026-09-06"})
    assert response.status_code == 200
    assert response.json()["timeline"] == []
    # A plan still needs at least one goal.
    assert client.post("/api/plan", json={"goals": [], "day": "2026-09-06"}).status_code == 400


# --- one active work context -------------------------------------------


def test_starting_a_goal_starts_its_block_and_activates_the_goal(clock, store):
    start, end = window(clock, -5)
    plan = store.save_plan("Ship it", [block(start, end, "build", goal_index=0)], day=None)
    goal_id = plan["goals"][0]["id"]

    work = store.start_work(goal_id=goal_id)
    assert work["goal"]["id"] == goal_id
    assert work["running_block"]["task"] == "build"
    assert work["running_block"]["run"]["state"] == "running"
    assert work["conflicts"] == []


def test_starting_a_block_activates_the_goal_it_serves(clock, store):
    start, end = window(clock, -5)
    plan = store.save_plan("Ship it", [block(start, end, "build", goal_index=0)], day=None)
    block_id = plan["timeline"][0]["block_id"]

    work = store.start_work(block_id=block_id)
    assert work["goal"]["status"] == "active"
    assert work["goal"]["id"] == plan["goals"][0]["id"]


def test_switching_work_leaves_exactly_one_thing_running(clock, store):
    first_start, first_end = window(clock, -120, 60)
    second_start, second_end = window(clock, -5)
    plan = store.save_plan(
        "One\nTwo",
        [
            block(first_start, first_end, "early", goal_index=0),
            block(second_start, second_end, "current", goal_index=1),
        ],
        day=None,
    )
    store.start_work(goal_id=plan["goals"][0]["id"])
    work = store.start_work(goal_id=plan["goals"][1]["id"])

    assert work["running_block"]["task"] == "current"
    assert work["goal"]["text"] == "Two"
    running = [r for r in store.block_runs(work["day"]) if r["state"] == "running"]
    assert len(running) == 1
    actives = [g for g in store.list_goals(work["day"]) if g["status"] == "active"]
    assert len(actives) == 1


def test_a_block_running_past_its_window_is_reported_as_a_conflict(clock, store):
    past_start, past_end = window(clock, -180, 60)
    plan = store.save_plan("Ship it", [block(past_start, past_end, "overrun", goal_index=0)], day=None)
    store.start_block(plan["day"], plan["timeline"][0]["block_id"])

    work = store.active_work(plan["day"])
    kinds = {c["kind"] for c in work["conflicts"]}
    assert "stale_block" in kinds
    assert any("past its scheduled end" in c["message"] for c in work["conflicts"])


def test_a_running_block_serving_another_goal_is_reported(clock, store):
    start, end = window(clock, -5)
    plan = store.save_plan("One\nTwo", [block(start, end, "build", goal_index=0)], day=None)
    store.start_block(plan["day"], plan["timeline"][0]["block_id"])
    store.set_goal_status(plan["goals"][1]["id"], "active")

    work = store.active_work(plan["day"])
    assert "goal_mismatch" in {c["kind"] for c in work["conflicts"]}


def test_focus_protecting_a_different_goal_is_reported(store):
    plan = store.save_plan("One\nTwo", [], day=None)
    store.set_goal_status(plan["goals"][0]["id"], "active")
    store.create_quiet(level="quiet", minutes=30, goal_id=plan["goals"][1]["id"])

    work = store.active_work(plan["day"])
    assert "focus_mismatch" in {c["kind"] for c in work["conflicts"]}


def test_starting_work_with_focus_binds_the_session_to_the_goal(store):
    plan = store.save_plan("Ship it", [], day=None)
    goal_id = plan["goals"][0]["id"]
    work = store.start_work(goal_id=goal_id, focus_minutes=30)
    assert work["focus"]["goal_id"] == goal_id
    assert work["conflicts"] == []


def test_stopping_work_pauses_the_block_and_ends_focus_without_judging(clock, store):
    start, end = window(clock, -5)
    plan = store.save_plan("Ship it", [block(start, end, "build", goal_index=0)], day=None)
    goal_id = plan["goals"][0]["id"]
    store.start_work(goal_id=goal_id, focus_minutes=30)

    work = store.stop_work(plan["day"])
    assert work["running_block"] is None
    assert work["focus"] is None
    # Stopping is not finishing: the goal keeps its status.
    assert store.get_goal(goal_id)["status"] == "active"
    assert store.block_run(plan["day"], plan["timeline"][0]["block_id"])["state"] == "paused"


def test_starting_a_goal_with_no_block_still_stops_a_stale_one(clock, store):
    past_start, past_end = window(clock, -180, 60)
    plan = store.save_plan("One\nTwo", [block(past_start, past_end, "old", goal_index=0)], day=None)
    store.start_block(plan["day"], plan["timeline"][0]["block_id"])

    work = store.start_work(goal_id=plan["goals"][1]["id"])
    assert work["running_block"] is None, "an unrelated block does not keep ticking"
    assert work["conflicts"] == []


def test_work_api_round_trip(clock, tmp_path):
    client = TestClient(create_app(str(tmp_path / "api.db")))
    start, end = window(clock, -5)
    plan = client.post(
        "/api/plan",
        json={"goals": [{"text": "Ship it"}], "timeline": [block(start, end, "build", goal_index=0)]},
    ).json()
    goal_id = plan["goals"][0]["id"]

    started = client.post("/api/work/start", json={"goal_id": goal_id})
    assert started.status_code == 200
    assert started.json()["running_block"]["run"]["state"] == "running"

    assert client.get("/api/work").json()["goal"]["id"] == goal_id
    assert client.get("/api/today").json()["active_work"]["goal"]["id"] == goal_id

    stopped = client.post("/api/work/stop", json={})
    assert stopped.json()["running_block"] is None


# --- atomic switching ---------------------------------------------------


def test_switching_goals_moves_focus_with_the_work(clock, store):
    """The bug: focus stayed bound to the goal you switched away from."""
    a_start, a_end = window(clock, -5)
    b_start, b_end = window(clock, 180)
    plan = store.save_plan(
        "Goal A\nGoal B",
        [block(a_start, a_end, "on A", goal_index=0), block(b_start, b_end, "on B", goal_index=1)],
        day=None,
    )
    a, b = [g["id"] for g in plan["goals"]]

    store.start_work(goal_id=a, focus_minutes=60)
    # The interface does not ask for focus again when a session already exists.
    work = store.start_work(goal_id=b)

    assert work["goal"]["id"] == b
    assert work["focus"]["goal_id"] == b, "focus follows the work"
    # start_work leaves no contradiction it controls. Working on B during A's
    # scheduled window is a real divergence from the plan, not a bug, so it is
    # reported with the action that resolves it.
    kinds = {c["kind"] for c in work["conflicts"]}
    assert "focus_mismatch" not in kinds and "goal_mismatch" not in kinds
    assert kinds <= {"off_schedule"}
    off = next(c for c in work["conflicts"] if c["kind"] == "off_schedule")
    assert off["action"] == "switch_work", "the fix is to move to the schedule, not end the work"


def test_carried_focus_keeps_its_level_and_remaining_time(store):
    plan = store.save_plan("A\nB", [], day=None)
    a, b = [g["id"] for g in plan["goals"]]
    store.start_work(goal_id=a, focus_minutes=45, focus_level="dormant")
    before = store.quiet_summary()["seconds_left"]

    work = store.start_work(goal_id=b)
    assert work["focus"]["level"] == "dormant"
    assert work["focus"]["seconds_left"] <= before
    assert work["focus"]["seconds_left"] > 0


def test_switching_back_to_the_focused_goal_leaves_the_session_alone(store):
    plan = store.save_plan("A\nB", [], day=None)
    a, b = [g["id"] for g in plan["goals"]]
    store.start_work(goal_id=a, focus_minutes=60)
    session = store.quiet_summary()["id"]
    store.start_work(goal_id=b)
    work = store.start_work(goal_id=a)
    assert work["focus"]["goal_id"] == a
    assert work["focus"]["id"] != session, "the original session was replaced, not resurrected"
    # Re-starting the same goal does not churn the session again.
    same = store.start_work(goal_id=a)
    assert same["focus"]["id"] == work["focus"]["id"]


def test_starting_work_without_focus_does_not_invent_one(store):
    plan = store.save_plan("A", [], day=None)
    work = store.start_work(goal_id=plan["goals"][0]["id"])
    assert work["focus"] is None


# --- one headline, one next action --------------------------------------


def test_next_action_always_describes_the_headline_goal(clock, store):
    """The bug: the headline came from the goal list and the action from the clock."""
    start, end = window(clock, -5)
    plan = store.save_plan(
        "Goal A\nGoal B",
        [block(start, end, "work on B", goal_index=1)],
        day=None,
    )
    a = plan["goals"][0]["id"]
    store.set_goal_status(a, "active")

    work = store.active_work(plan["day"])
    assert work["goal"]["id"] == a
    assert work["next_action"]["text"] != "work on B", "never an action for another goal"
    assert work["next_action"]["source"] == "goal"
    # The divergence is surfaced instead, before anything is even running.
    assert "scheduled_elsewhere" in {c["kind"] for c in work["conflicts"]}


def test_next_action_prefers_the_running_block(clock, store):
    start, end = window(clock, -5)
    plan = store.save_plan("A", [block(start, end, "build", goal_index=0)], day=None)
    work = store.start_work(goal_id=plan["goals"][0]["id"])
    assert work["next_action"]["source"] == "running_block"
    assert work["next_action"]["text"] == "build"
    assert work["next_action"]["minutes_left"] > 0


def test_next_action_falls_back_through_scheduled_then_upcoming_then_the_goal(clock, store):
    start, end = window(clock, -5)
    later_start, later_end = window(clock, 120)
    plan = store.save_plan("A", [block(start, end, "now", goal_index=0)], day=None)
    scheduled = store.active_work(plan["day"])
    assert scheduled["next_action"]["source"] == "scheduled_block"
    assert scheduled["next_action"]["text"] == "now"

    store.save_plan("A", [block(later_start, later_end, "later", goal_index=0)], day=plan["day"])
    upcoming = store.active_work(plan["day"])
    assert upcoming["next_action"]["source"] == "upcoming_block"
    assert upcoming["next_action"]["starts_at"] == later_start

    store.save_plan("A", [], day=plan["day"])
    bare = store.active_work(plan["day"])
    assert bare["next_action"] == {"text": "A", "source": "goal"}


def test_next_action_prefers_goal_next_step_over_outcome_text(store):
    plan = store.save_plan(
        "",
        [],
        day=None,
        goals=[{"text": "Ship password reset", "next_step": "Write the expired-token integration test"}],
    )
    work = store.active_work(plan["day"])
    assert work["next_action"] == {
        "text": "Write the expired-token integration test",
        "source": "goal_next_step",
    }


def test_a_settled_day_has_no_headline_and_no_next_action(store):
    plan = store.save_plan("A", [], day=None)
    store.set_goal_status(plan["goals"][0]["id"], "done")
    work = store.active_work(plan["day"])
    assert work["goal"] is None
    assert work["next_action"] is None


def test_a_deferred_goal_is_not_picked_up_as_the_headline(store):
    plan = store.save_plan("A", [], day=None)
    store.set_goal_status(plan["goals"][0]["id"], "deferred")
    assert store.active_work(plan["day"])["goal"] is None


def test_every_conflict_names_the_action_that_resolves_it(clock, store):
    past_start, past_end = window(clock, -180, 60)
    now_start, now_end = window(clock, -5)
    plan = store.save_plan(
        "A\nB",
        [block(past_start, past_end, "old", goal_index=0), block(now_start, now_end, "now", goal_index=1)],
        day=None,
    )
    store.start_block(plan["day"], plan["timeline"][0]["block_id"])
    store.set_goal_status(plan["goals"][1]["id"], "active")

    conflicts = store.active_work(plan["day"])["conflicts"]
    assert conflicts, "this state really is contradictory"
    for conflict in conflicts:
        assert conflict["action"] in {"finish_block", "switch_work"}
        assert conflict.get("block_id") or conflict.get("goal_id"), "the action has a target"


# --- system-enforced closure -------------------------------------------


def test_the_backend_refuses_to_close_an_unjudged_day(store):
    """The gap: the button was disabled, but the API accepted the ack anyway."""
    plan = store.save_plan("Judged\nNever judged", [], day="2026-09-05")
    store.set_goal_status(plan["goals"][0]["id"], "done")
    store.save_recap("2026-09-05", [{"kicker": "Recap"}], phone_synced=False)

    with pytest.raises(ValueError, match="still needs an outcome"):
        store.ack_recap("2026-09-05")
    assert store.get_recap("2026-09-05")["acked_at"] is None

    store.set_goal_status(plan["goals"][1]["id"], "deferred", "ran out of day")
    assert store.ack_recap("2026-09-05")["acked_at"]


def test_the_refusal_names_the_goals_that_are_missing_an_outcome(store):
    store.save_plan("One\nTwo\nThree\nFour", [], day="2026-09-05")
    store.save_recap("2026-09-05", [{"kicker": "Recap"}], phone_synced=False)
    with pytest.raises(ValueError) as excinfo:
        store.ack_recap("2026-09-05")
    message = str(excinfo.value)
    assert "One, Two, Three" in message and "1 more" in message


def test_every_settled_status_counts_as_judged(store):
    for index, status in enumerate(("done", "partial", "deferred", "dropped")):
        day = f"2026-08-0{index + 1}"
        plan = store.save_plan("A goal", [], day=day)
        store.set_goal_status(plan["goals"][0]["id"], status)
        store.save_recap(day, [{"kicker": "Recap"}], phone_synced=False)
        assert store.ack_recap(day)["acked_at"], f"{status} should close the day"


def test_a_day_with_no_plan_still_closes(store):
    store.save_recap("2026-09-05", [{"kicker": "Recap"}], phone_synced=False)
    assert store.ack_recap("2026-09-05")["acked_at"]


def test_the_ack_api_reports_the_refusal(tmp_path):
    from timeless.clock import due_recap_day

    client = TestClient(create_app(str(tmp_path / "api.db")))
    day = due_recap_day()
    client.post("/api/plan", json={"goals": [{"text": "Never judged"}], "day": day})
    client.post("/api/recap/generate", json={"skip_phone": True})

    refused = client.post("/api/recap/ack", json={})
    assert refused.status_code == 400
    assert "still needs an outcome" in refused.json()["detail"]
    assert client.get("/api/today").json()["needs_recap"] is True

    goal_id = client.get(f"/api/goals?day={day}").json()["goals"][0]["id"]
    client.patch(f"/api/goals/{goal_id}", json={"status": "deferred", "note": "ran out of day"})
    assert client.post("/api/recap/ack", json={}).status_code == 200
    assert client.get("/api/today").json()["needs_recap"] is False


# --- transactional work switching --------------------------------------


def test_a_failure_part_way_through_start_work_changes_nothing(clock, store, monkeypatch):
    start, end = window(clock, -5)
    plan = store.save_plan("A\nB", [block(start, end, "on A", goal_index=0)], day=None)
    a, b = [g["id"] for g in plan["goals"]]
    store.start_work(goal_id=a, focus_minutes=60)

    before = store.active_work(plan["day"])
    assert before["goal"]["id"] == a

    # The focus step is the last thing start_work does; if it fails, the goal and
    # block changes made before it must not survive.
    def boom(*args, **kwargs):
        raise RuntimeError("focus backend unavailable")

    monkeypatch.setattr(Store, "_rebind_focus", boom)
    with pytest.raises(RuntimeError):
        store.start_work(goal_id=b)

    after = store.active_work(plan["day"])
    assert after["goal"]["id"] == a, "the goal switch was rolled back"
    assert after["focus"]["goal_id"] == a, "focus never moved"
    assert [g["status"] for g in store.list_goals(plan["day"])] == [
        s for s in ("active", "planned")
    ]


def test_a_rolled_back_switch_leaves_no_stray_block_run(clock, store, monkeypatch):
    a_start, a_end = window(clock, -5)
    b_start, b_end = window(clock, -5)
    plan = store.save_plan("A", [block(a_start, a_end, "on A", goal_index=0)], day=None)
    goal = plan["goals"][0]["id"]

    monkeypatch.setattr(Store, "_rebind_focus", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("nope")))
    with pytest.raises(RuntimeError):
        store.start_work(goal_id=goal)

    assert store.block_runs(plan["day"]) == [], "no half-started run was left behind"
    assert store.get_goal(goal)["status"] == "planned"


def test_the_store_still_commits_normally_outside_a_transaction(store):
    plan = store.save_plan("A", [], day="2026-09-06")
    store.set_goal_status(plan["goals"][0]["id"], "done")
    # A fresh connection to the same file sees the committed row.
    reopened = Store(store.db_path)
    assert reopened.list_goals("2026-09-06")[0]["status"] == "done"


class _FailingSql:
    """A connection whose matching statements fail, standing in for a bad disk."""

    def __init__(self, real, match="SAVEPOINT"):
        self._real = real
        self._match = match

    def execute(self, sql, *args):
        if self._match in str(sql).upper():
            raise RuntimeError("disk gave up")
        return self._real.execute(sql, *args)

    def __getattr__(self, name):
        return getattr(self._real, name)


def _with_failing_sql(store, match):
    real = store.conn
    store.conn = _FailingSql(real, match)
    return real


def test_a_database_failure_inside_a_transaction_does_not_poison_the_store(store):
    """_in_atomic must clear even when the savepoint machinery itself fails."""
    real = _with_failing_sql(store, "SAVEPOINT")
    try:
        with pytest.raises(RuntimeError):
            with store._atomic():
                pass
    finally:
        store.conn = real

    assert store._in_atomic is False, "the store is still usable"
    # And ordinary writes still commit afterwards.
    store.save_plan("A", [], day="2026-09-06")
    assert Store(store.db_path).list_goals("2026-09-06")[0]["text"] == "A"


def test_a_failed_rollback_discards_the_transaction_rather_than_committing_half(store):
    """The gap: the outer finally committed even when the undo had failed."""
    plan = store.save_plan("Goal A\nGoal B", [], day="2026-09-06")
    a, b = [g["id"] for g in plan["goals"]]
    store.start_work(day="2026-09-06", goal_id=a, focus_minutes=60)

    real = store.conn
    store.conn = _FailingSql(real, "ROLLBACK TO SAVEPOINT")
    try:
        with pytest.raises(RuntimeError):
            with store._atomic():
                store.set_goal_status(b, "active")
                # A later step fails, so the block's writes must be undone.
                raise RuntimeError("focus step failed")
    finally:
        store.conn = real

    # Nothing from the failed block reached the file.
    fresh = Store(store.db_path)
    statuses = {g["text"]: g["status"] for g in fresh.list_goals("2026-09-06")}
    assert statuses == {"Goal A": "active", "Goal B": "planned"}
    assert fresh.quiet_summary()["goal_id"] == a, "focus never moved"
    assert store._in_atomic is False


def test_a_failed_release_also_discards_rather_than_committing(store):
    store.save_plan("Goal A", [], day="2026-09-06")
    real = store.conn
    store.conn = _FailingSql(real, "RELEASE SAVEPOINT")
    try:
        with pytest.raises(RuntimeError):
            with store._atomic():
                store.save_plan("Rewritten", [], day="2026-09-06")
    finally:
        store.conn = real

    assert [g["text"] for g in Store(store.db_path).list_goals("2026-09-06")] == ["Goal A"]
    assert store._in_atomic is False


def test_the_store_recovers_after_a_failed_transaction(store):
    real = store.conn
    store.conn = _FailingSql(real, "ROLLBACK TO SAVEPOINT")
    try:
        with pytest.raises(RuntimeError):
            with store._atomic():
                raise RuntimeError("something went wrong")
    finally:
        store.conn = real

    # The connection is not left holding an open transaction.
    store.save_plan("After the failure", [], day="2026-09-07")
    assert Store(store.db_path).list_goals("2026-09-07")[0]["text"] == "After the failure"


# --- a database that cannot be unwound ----------------------------------


class _FailingUnwind:
    """Both the savepoint rollback and the connection rollback fail."""

    def __init__(self, real):
        self._real = real

    def execute(self, sql, *args):
        if "ROLLBACK TO SAVEPOINT" in str(sql).upper():
            raise RuntimeError("savepoint rollback failed")
        return self._real.execute(sql, *args)

    def rollback(self):
        raise RuntimeError("connection rollback failed")

    def __getattr__(self, name):
        return getattr(self._real, name)


def _statuses(path, day="2026-09-06"):
    fresh = Store(path)
    try:
        return {g["text"]: g["status"] for g in fresh.list_goals(day)}
    finally:
        fresh.close()


def test_an_unrecoverable_rollback_poisons_the_store_instead_of_leaking_later(store):
    """The gap: the abandoned transaction stayed open and the next commit published it."""
    plan = store.save_plan("Goal A\nGoal B", [], day="2026-09-06")
    a, b = [g["id"] for g in plan["goals"]]
    store.start_work(day="2026-09-06", goal_id=a, focus_minutes=60)
    before = _statuses(store.db_path)

    store.conn = _FailingUnwind(store.conn)
    with pytest.raises(RuntimeError):
        with store._atomic():
            store.set_goal_status(b, "active")
            raise RuntimeError("focus step failed")

    assert store.poisoned is True
    # An unrelated write can no longer publish the abandoned change.
    with pytest.raises(StoreUnavailable):
        store.heartbeat("sensor", "unrelated write")
    assert _statuses(store.db_path) == before


def test_a_poisoned_store_refuses_reads_as_well_as_writes(store):
    store.save_plan("A", [], day="2026-09-06")
    store.conn = _FailingUnwind(store.conn)
    with pytest.raises(RuntimeError):
        with store._atomic():
            raise RuntimeError("boom")

    for call in (lambda: store.list_goals("2026-09-06"), lambda: store.get_plan("2026-09-06")):
        with pytest.raises(StoreUnavailable):
            call()


def test_reconnecting_recovers_the_store_from_the_last_consistent_state(store):
    plan = store.save_plan("Goal A\nGoal B", [], day="2026-09-06")
    store.set_goal_status(plan["goals"][0]["id"], "active")
    before = _statuses(store.db_path)

    store.conn = _FailingUnwind(store.conn)
    with pytest.raises(RuntimeError):
        with store._atomic():
            store.set_goal_status(plan["goals"][1]["id"], "active")
            raise RuntimeError("boom")

    store.reconnect()
    assert store.poisoned is False
    assert _statuses(store.db_path) == before
    store.heartbeat("sensor", "works again")
    assert store.heartbeats()


def test_a_failed_commit_is_reported_rather_than_swallowed(store):
    """The gap: a commit failure was caught and the caller was told it worked.

    With this driver the write is already durable by then — releasing the
    outermost savepoint empties the stack and commits — so the final
    `conn.commit()` is belt and braces. It must still never report success it
    cannot vouch for.
    """

    class FailingCommit:
        def __init__(self, real):
            self._real = real

        def commit(self):
            raise RuntimeError("commit failed")

        def __getattr__(self, name):
            return getattr(self._real, name)

    store.save_plan("A", [], day="2026-09-06")
    store.conn = FailingCommit(store.conn)
    with pytest.raises(RuntimeError, match="commit failed"):
        with store._atomic():
            store.save_plan("Rewritten", [], day="2026-09-06")

    assert store.poisoned is True, "a connection that cannot commit is not trusted"


def test_releasing_the_savepoint_is_what_makes_a_transaction_durable(store):
    """Documents the driver behaviour the unwind logic depends on."""
    with store._atomic():
        store.save_plan("Committed by release", [], day="2026-09-06")
        assert store._in_atomic is True
    assert _statuses(store.db_path) == {"Committed by release": "planned"}
    assert store.conn.in_transaction is False


def test_the_api_reports_a_poisoned_store_as_unavailable(tmp_path, monkeypatch):
    path = str(tmp_path / "poison.db")
    poisoned = Store(path)
    poisoned.save_plan("A", [], day="2026-09-06")
    poisoned.conn = _FailingUnwind(poisoned.conn)
    with pytest.raises(RuntimeError):
        with poisoned._atomic():
            raise RuntimeError("boom")
    assert poisoned.poisoned is True

    # Hand the already-poisoned store to the app the way create_app builds one.
    monkeypatch.setattr("timeless.app.Store", lambda _path: poisoned)
    client = TestClient(create_app(path), raise_server_exceptions=False)

    response = client.get("/api/today")
    assert response.status_code == 503
    assert "reconnect" in response.json()["detail"]


def test_the_refusal_reads_correctly_for_one_goal_and_for_several(store):
    store.save_plan("Only one", [], day="2026-09-05")
    store.save_recap("2026-09-05", [{"kicker": "Recap"}], phone_synced=False)
    with pytest.raises(ValueError, match=r"^1 goal still needs an outcome"):
        store.ack_recap("2026-09-05")

    store.save_plan("One\nTwo", [], day="2026-09-04")
    store.save_recap("2026-09-04", [{"kicker": "Recap"}], phone_synced=False)
    with pytest.raises(ValueError, match=r"^2 goals still need an outcome"):
        store.ack_recap("2026-09-04")


def test_the_window_helper_refuses_a_wrapping_block(clock):
    """The guard on the bug this file used to have.

    A window built from the real evening clock produced 23:30 to 00:30, which
    sorts before every other block and broke the suite after about 21:00. The
    helper must reject that outright rather than return times that only fail
    later, in an assertion far from the cause.
    """
    late = clock.replace(hour=23, minute=30)
    with pytest.raises(AssertionError, match="must not cross midnight"):
        window(late, 120)
    # And the frozen noon base has room either side.
    assert window(clock, -180) == ("09:00", "10:00")
    assert window(clock, 180) == ("15:00", "16:00")


def test_the_frozen_clock_is_what_the_store_reads(clock):
    from timeless.store import _local_minute

    assert _local_minute() == 12 * 60, "windows and active_work must agree on now"
