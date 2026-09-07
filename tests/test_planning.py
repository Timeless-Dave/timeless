import time

import pytest
from fastapi.testclient import TestClient

from timeless.app import create_app
from timeless.planning import block_issues, meeting_conflicts, plan_warnings, planned_minutes
from timeless.store import Store


@pytest.fixture
def store(tmp_path):
    return Store(str(tmp_path / "planning.db"))


def block(start="09:00", end="10:00", task="work", **extra):
    return {"start": start, "end": end, "task": task, **extra}


def test_a_block_cannot_end_before_it_starts():
    issues = block_issues([block("10:00", "09:00")])
    assert len(issues) == 1
    assert issues[0]["level"] == "error"
    assert "ends before it starts" in issues[0]["message"]


def test_equal_start_and_end_is_an_error():
    assert block_issues([block("09:00", "09:00")])


def test_overlapping_blocks_are_reported_once():
    issues = block_issues([block("09:00", "11:00"), block("10:00", "12:00")])
    assert len(issues) == 1
    assert "overlap" in issues[0]["message"]


def test_back_to_back_blocks_are_fine():
    assert block_issues([block("09:00", "10:00"), block("10:00", "11:00")]) == []


def test_loose_legacy_times_are_left_alone():
    # Plans stored before time inputs used values like "9"; they must still save.
    assert block_issues([block("9", "10")]) == []
    assert block_issues([block("25:00", "26:00")]) == []


def test_capacity_and_long_blocks_warn_but_never_block():
    warnings = plan_warnings([block("06:00", "23:00")])
    assert all(w["level"] == "warning" for w in warnings)
    assert any("more than most days hold" in w["message"] for w in warnings)
    assert any("without a break" in w["message"] for w in warnings)


def test_too_many_goals_warns():
    goals = [{"text": f"goal {i}"} for i in range(7)]
    assert any("7 goals" in w["message"] for w in plan_warnings([], goals))
    assert plan_warnings([], [{"text": "one"}]) == []


def test_planned_minutes_ignores_unparseable_and_inverted_blocks():
    assert planned_minutes([block("09:00", "11:30"), block("10:00", "09:00"), block("9", "10")]) == 150


def test_meeting_conflicts_are_warnings():
    conflicts = meeting_conflicts(
        [block("09:00", "11:00")],
        [{"start_at": "2026-09-06T10:00:00", "end_at": "2026-09-06T10:30:00", "title": "Standup"}],
    )
    assert len(conflicts) == 1
    assert conflicts[0]["level"] == "warning"
    assert "Standup" in conflicts[0]["message"]


def test_saving_an_impossible_schedule_is_refused(store):
    with pytest.raises(ValueError, match="ends before it starts"):
        store.save_plan("A", [block("10:00", "09:00")], day="2026-09-06")
    with pytest.raises(ValueError, match="overlap"):
        store.save_plan("A", [block("09:00", "11:00"), block("10:00", "12:00")], day="2026-09-06")
    # An overloaded but possible day still saves.
    assert store.save_plan("A", [block("06:00", "23:00")], day="2026-09-06")


def test_api_rejects_an_impossible_schedule(tmp_path):
    client = TestClient(create_app(str(tmp_path / "api.db")))
    bad = client.post(
        "/api/plan",
        json={"goals": [{"text": "A"}], "timeline": [block("10:00", "09:00")], "day": "2026-09-06"},
    )
    assert bad.status_code == 400
    assert "ends before it starts" in bad.json()["detail"]


def test_a_goal_with_history_is_archived_not_destroyed(store):
    plan = store.save_plan("Worked on\nUntouched", [block()], day="2026-09-06")
    store.set_goal_status(plan["goals"][0]["id"], "partial", "half of it")

    after = store.save_plan("", [block()], day="2026-09-06", goals=[{"text": "Something else"}])
    assert [g["text"] for g in after["goals"]] == ["Something else"]

    archived = store.archived_goals("2026-09-06")
    assert [(g["text"], g["status"], g["note"]) for g in archived] == [("Worked on", "partial", "half of it")]


def test_a_goal_that_never_happened_is_simply_removed(store):
    store.save_plan("Keep\nTypo", [block()], day="2026-09-06")
    store.save_plan("Keep", [block()], day="2026-09-06")
    assert store.archived_goals("2026-09-06") == []


def test_archived_goals_leave_progress_and_matching(store):
    plan = store.save_plan("Done thing\nOther", [block()], day="2026-09-06")
    store.set_goal_status(plan["goals"][0]["id"], "done")
    after = store.save_plan("Other", [block()], day="2026-09-06")
    assert after["goal_progress"]["total"] == 1
    assert after["goal_progress"]["done"] == 0
    # Re-adding the same text starts a fresh goal rather than reviving the archived one.
    again = store.save_plan("Other\nDone thing", [block()], day="2026-09-06")
    assert [g["status"] for g in again["goals"]] == ["planned", "planned"]


def test_restoring_an_archived_goal_returns_it_with_its_history(store):
    plan = store.save_plan("Worked on\nOther", [block()], day="2026-09-06")
    store.set_goal_status(plan["goals"][0]["id"], "partial", "half of it")
    store.save_plan("Other", [block()], day="2026-09-06")

    goal_id = store.archived_goals("2026-09-06")[0]["id"]
    restored = store.restore_goal(goal_id)
    assert restored["status"] == "partial"
    assert restored["note"] == "half of it"
    assert [g["text"] for g in store.list_goals("2026-09-06")] == ["Worked on", "Other"]
    # The legacy outcomes projection is resynced.
    assert store.get_plan("2026-09-06")["outcomes"] == "Worked on\nOther"


def test_blocks_get_stable_ids_that_survive_an_edit(store):
    plan = store.save_plan("A", [block(task="code"), block("10:00", "11:00", "review")], day="2026-09-06")
    ids = [b["block_id"] for b in plan["timeline"]]
    assert all(ids) and len(set(ids)) == 2

    edited = [dict(plan["timeline"][0], task="code more"), plan["timeline"][1]]
    again = store.save_plan("A", edited, day="2026-09-06")
    assert [b["block_id"] for b in again["timeline"]] == ids


def test_a_block_runs_pauses_and_finishes(store):
    plan = store.save_plan("A", [block()], day="2026-09-06")
    block_id = plan["timeline"][0]["block_id"]

    store.start_block("2026-09-06", block_id, plan["goals"][0]["id"])
    time.sleep(1.05)
    running = store.block_run("2026-09-06", block_id)
    assert running["state"] == "running"
    assert running["elapsed_seconds"] >= 1

    paused = store.pause_block("2026-09-06", block_id)
    assert paused["state"] == "paused"
    assert paused["elapsed_seconds"] >= 1
    # A paused run stops accumulating.
    time.sleep(0.2)
    assert store.block_run("2026-09-06", block_id)["elapsed_seconds"] == paused["elapsed_seconds"]

    done = store.finish_block("2026-09-06", block_id)
    assert done["state"] == "done" and done["ended_at"]


def test_only_one_block_runs_at_a_time(store):
    plan = store.save_plan("A", [block(), block("10:00", "11:00", "review")], day="2026-09-06")
    first, second = [b["block_id"] for b in plan["timeline"]]
    store.start_block("2026-09-06", first)
    store.start_block("2026-09-06", second)
    assert store.block_run("2026-09-06", first)["state"] == "paused"
    assert store.block_run("2026-09-06", second)["state"] == "running"


def test_a_finished_block_cannot_be_restarted(store):
    plan = store.save_plan("A", [block()], day="2026-09-06")
    block_id = plan["timeline"][0]["block_id"]
    store.finish_block("2026-09-06", block_id)
    with pytest.raises(ValueError, match="already finished"):
        store.start_block("2026-09-06", block_id)


def test_pausing_something_never_started_is_an_error(store):
    with pytest.raises(ValueError, match="never started"):
        store.pause_block("2026-09-06", "nope")


def test_observed_minutes_are_attributed_to_the_block_s_goal(store):
    plan = store.save_plan(
        "Study\nWrite",
        [block("09:00", "12:00", "study", goal_index=0), block("13:00", "15:00", "write", goal_index=1)],
        day="2026-09-06",
    )
    study, write = [g["id"] for g in plan["goals"]]
    from timeless.clock import zone
    from datetime import datetime, timezone as tz

    def at(hour):
        local = datetime(2026, 9, 6, hour, 30, tzinfo=zone())
        return local.astimezone(tz.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    store.add_activity(source="aw", source_id="a", ts=at(10), duration_seconds=20 * 60, app="Code", title="study notes")
    store.add_activity(source="aw", source_id="b", ts=at(14), duration_seconds=20 * 60, app="Code", title="writing")
    store.add_activity(source="aw", source_id="c", ts=at(20), duration_seconds=20 * 60, app="Code", title="evening")

    goal_minutes = store.productivity_on_day("2026-09-06")["goal_minutes"]
    assert goal_minutes == {str(study): 20, str(write): 20}, "time outside any block belongs to no goal"


def test_block_and_goal_apis(tmp_path):
    client = TestClient(create_app(str(tmp_path / "api.db")))
    plan = client.post(
        "/api/plan",
        json={"goals": [{"text": "A"}], "timeline": [block(goal_index=0)], "day": "2026-09-06"},
    ).json()
    block_id = plan["timeline"][0]["block_id"]

    started = client.post(f"/api/blocks/{block_id}/start", json={"day": "2026-09-06"})
    assert started.status_code == 200 and started.json()["state"] == "running"
    assert client.post(f"/api/blocks/{block_id}/finish", json={"day": "2026-09-06"}).json()["state"] == "done"
    assert client.post(f"/api/blocks/{block_id}/start", json={"day": "2026-09-06"}).status_code == 400
    assert client.post(f"/api/blocks/{block_id}/teleport", json={"day": "2026-09-06"}).status_code == 404

    client.post("/api/plan", json={"goals": [{"text": "B"}], "timeline": [block()], "day": "2026-09-06"})
    archived = client.get("/api/goals/archived?day=2026-09-06").json()["goals"]
    assert archived == [], "an untouched goal is removed, not archived"


def test_focus_can_be_bound_to_a_goal(tmp_path):
    client = TestClient(create_app(str(tmp_path / "api.db")))
    plan = client.post(
        "/api/plan", json={"goals": [{"text": "A"}], "timeline": [block()], "day": "2026-09-06"}
    ).json()
    goal_id = plan["goals"][0]["id"]
    quiet = client.post("/api/quiet", json={"level": "quiet", "minutes": 30, "goal_id": goal_id})
    assert quiet.status_code == 200
    assert quiet.json()["goal_id"] == goal_id


def test_every_spa_route_is_served(tmp_path):
    from timeless.app import FRONTEND_DIST

    client = TestClient(create_app(str(tmp_path / "spa.db")))
    for route in ("/", "/gate", "/halt", "/recap", "/ops"):
        response = client.get(route)
        assert response.status_code == 200, f"{route} is not served"
        if FRONTEND_DIST.exists():
            assert "text/html" in response.headers["content-type"]
