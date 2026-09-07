import pytest
from fastapi.testclient import TestClient

from timeless.app import create_app
from timeless.db import connect
from timeless.store import Store, goal_progress


@pytest.fixture
def store(tmp_path):
    return Store(str(tmp_path / "goals.db"))


def block(task="code", start="09:00", end="10:00", **extra):
    return {"start": start, "end": end, "task": task, **extra}


def test_saved_goals_get_identity_and_position(store):
    plan = store.save_plan("Ship the loop\nRead the paper", [block()], day="2026-09-06")
    assert [g["text"] for g in plan["goals"]] == ["Ship the loop", "Read the paper"]
    assert [g["position"] for g in plan["goals"]] == [0, 1]
    assert all(g["status"] == "planned" for g in plan["goals"])
    assert plan["outcomes"] == "Ship the loop\nRead the paper"


def test_resaving_a_plan_preserves_goal_status(store):
    plan = store.save_plan("Ship the loop\nRead the paper", [block()], day="2026-09-06")
    store.set_goal_status(plan["goals"][0]["id"], "done")
    again = store.save_plan("Ship the loop\nRead the paper", [block("write")], day="2026-09-06")
    assert [(g["text"], g["status"]) for g in again["goals"]] == [
        ("Ship the loop", "done"),
        ("Read the paper", "planned"),
    ]


def test_only_one_goal_is_active_per_day(store):
    plan = store.save_plan("A\nB", [block()], day="2026-09-06")
    first, second = plan["goals"]
    store.set_goal_status(first["id"], "active")
    store.set_goal_status(second["id"], "active")
    statuses = {g["text"]: g["status"] for g in store.list_goals("2026-09-06")}
    assert statuses == {"A": "planned", "B": "active"}


def test_finishing_a_goal_stamps_a_completion_time(store):
    plan = store.save_plan("A", [block()], day="2026-09-06")
    done = store.set_goal_status(plan["goals"][0]["id"], "partial", note="ran out of time")
    assert done["completed_at"]
    assert done["note"] == "ran out of time"


def test_unknown_status_is_rejected(store):
    plan = store.save_plan("A", [block()], day="2026-09-06")
    with pytest.raises(ValueError):
        store.set_goal_status(plan["goals"][0]["id"], "finished-ish")


def test_blocks_link_to_goals_by_position_and_survive_a_round_trip(store):
    plan = store.save_plan(
        "A\nB",
        [block("code", goal_index=0), block("read", "10:00", "11:00", goal_index=1)],
        day="2026-09-06",
    )
    ids = [g["id"] for g in plan["goals"]]
    assert [b["goal_id"] for b in plan["timeline"]] == ids
    again = store.save_plan("A\nB", plan["timeline"], day="2026-09-06")
    assert [b["goal_id"] for b in again["timeline"]] == ids


def test_block_pointing_at_a_missing_goal_is_left_unlinked(store):
    plan = store.save_plan("A", [block(goal_id=9999)], day="2026-09-06")
    assert "goal_id" not in plan["timeline"][0]


def test_carry_forward_offers_only_unfinished_goals(store):
    plan = store.save_plan("Done thing\nOpen thing", [block()], day="2026-09-05")
    store.set_goal_status(plan["goals"][0]["id"], "done")
    candidates = store.carry_forward_candidates("2026-09-06")
    assert [g["text"] for g in candidates] == ["Open thing"]


def test_carrying_a_goal_forward_defers_the_source_and_counts_the_slip(store):
    monday = store.save_plan("Open thing", [block()], day="2026-09-05")
    source = monday["goals"][0]["id"]
    tuesday = store.save_plan(
        "",
        [block()],
        day="2026-09-06",
        goals=[{"text": "Open thing", "carried_from": source}],
    )
    assert tuesday["goals"][0]["deferred_count"] == 1
    assert store.list_goals("2026-09-05")[0]["status"] == "deferred"
    # Already pulled forward, so it is no longer offered again.
    assert store.carry_forward_candidates("2026-09-06") == []


def test_deferral_depth_accumulates_across_days(store):
    day_one = store.save_plan("Slippery task", [block()], day="2026-09-04")
    day_two = store.save_plan(
        "", [block()], day="2026-09-05", goals=[{"text": "Slippery task", "carried_from": day_one["goals"][0]["id"]}]
    )
    day_three = store.save_plan(
        "", [block()], day="2026-09-06", goals=[{"text": "Slippery task", "carried_from": day_two["goals"][0]["id"]}]
    )
    assert day_three["goals"][0]["deferred_count"] == 2


def test_removing_a_goal_from_the_plan_deletes_it(store):
    store.save_plan("A\nB", [block()], day="2026-09-06")
    plan = store.save_plan("A", [block()], day="2026-09-06")
    assert [g["text"] for g in plan["goals"]] == ["A"]


def test_a_plan_needs_at_least_one_goal(store):
    with pytest.raises(ValueError):
        store.save_plan("   ", [block()], day="2026-09-06")
    with pytest.raises(ValueError):
        store.save_plan("", [block()], day="2026-09-06", goals=[{"text": "  "}])


def test_progress_separates_completion_from_dropped_work():
    goals = [
        {"status": "done"},
        {"status": "partial"},
        {"status": "planned"},
        {"status": "dropped"},
    ]
    progress = goal_progress(goals)
    assert progress["done"] == 1
    assert progress["open"] == 1
    # Dropped work leaves the denominator rather than counting as a failure.
    assert progress["percent"] == 50
    assert goal_progress([])["percent"] is None


def test_legacy_outcomes_are_backfilled_into_goal_rows(tmp_path):
    path = tmp_path / "legacy.db"
    conn = connect(path)
    conn.execute("DELETE FROM plan_goals")
    conn.execute(
        "INSERT INTO daily_plans(day, outcomes, timeline, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
        ("2026-09-01", "- First win\n2. Second win", "[]", "2026-09-01T08:00:00Z", "2026-09-01T08:00:00Z"),
    )
    conn.commit()
    conn.close()

    reopened = Store(str(path))
    assert [g["text"] for g in reopened.list_goals("2026-09-01")] == ["First win", "Second win"]


def test_goal_api_round_trip(tmp_path):
    client = TestClient(create_app(str(tmp_path / "api.db")))
    saved = client.post(
        "/api/plan",
        json={"goals": [{"text": "Ship it"}], "timeline": [block()], "day": "2026-09-06"},
    ).json()
    goal_id = saved["goals"][0]["id"]

    patched = client.patch(f"/api/goals/{goal_id}", json={"status": "done", "note": "shipped"})
    assert patched.status_code == 200
    assert patched.json()["status"] == "done"

    listed = client.get("/api/goals?day=2026-09-06").json()
    assert listed["goal_progress"]["done"] == 1
    assert listed["goal_progress"]["percent"] == 100

    assert client.patch(f"/api/goals/{goal_id}", json={"status": "nonsense"}).status_code == 400
    assert client.patch("/api/goals/9999", json={"status": "done"}).status_code == 400


def test_today_reports_goal_progress_and_carry_forward(tmp_path):
    app = create_app(str(tmp_path / "today.db"))
    client = TestClient(app)
    day = client.get("/api/today").json()["day"]
    client.post("/api/plan", json={"goals": [{"text": "Only goal"}], "timeline": [block()], "day": day})

    today = client.get("/api/today").json()
    assert today["goal_progress"]["total"] == 1
    assert today["goal_progress"]["percent"] == 0
    assert today["carry_forward"] == []
