import pytest
from fastapi.testclient import TestClient

from timeless.app import create_app
from timeless.productivity import humanize_title, productivity_summary
from timeless.recap import build_cards, day_stats
from timeless.store import Store


@pytest.fixture
def store(tmp_path):
    return Store(str(tmp_path / "reflect.db"))


def block(task="code"):
    return {"start": "09:00", "end": "10:00", "task": task}


def sample(title, category, productivity, minutes):
    return {
        "category": category,
        "productivity": productivity,
        "duration_seconds": minutes * 60,
        "title": title,
        "app": "",
        "host": "",
    }


def test_lesson_is_saved_and_clearable(store):
    assert store.get_reflection("2026-09-06")["lesson"] is None
    assert store.save_reflection("2026-09-06", "  Start with the hard one.  ")["lesson"] == "Start with the hard one."
    assert store.save_reflection("2026-09-06", "")["lesson"] is None


def test_a_correction_overrides_the_classifier(store):
    store.save_plan("Study algorithms", [block()], day="2026-09-06")
    rows = [sample("Recommended videos", "distraction", "distracting", 20)]

    before = productivity_summary(rows, store.get_plan("2026-09-06"))
    assert before["minutes"]["distracting"] == 20
    assert before["evidence"][0]["corrected"] is False

    after = productivity_summary(
        rows, store.get_plan("2026-09-06"), corrections={"Recommended videos": "aligned"}
    )
    assert after["minutes"] == {"aligned": 20, "productive_off_plan": 0, "distracting": 0, "unknown": 0}
    assert after["evidence"][0]["corrected"] is True
    assert after["corrections"] == 1


def test_corrections_are_stored_per_day_and_applied_by_the_store(store):
    store.save_plan("Study algorithms", [block()], day="2026-09-06")
    store.add_activity(
        source="aw", source_id="w1", ts="2026-09-06T15:00:00Z",
        duration_seconds=20 * 60, app="Chrome", title="Recommended videos", host="youtube.com",
    )
    assert store.productivity_on_day("2026-09-06")["minutes"]["distracting"] == 20

    store.correct_activity("2026-09-06", "Recommended videos", "aligned")
    assert store.productivity_on_day("2026-09-06")["minutes"]["aligned"] == 20
    assert store.activity_corrections("2026-09-05") == {}


def test_a_correction_is_replaced_not_duplicated(store):
    store.correct_activity("2026-09-06", "Thing", "aligned")
    store.correct_activity("2026-09-06", "Thing", "distracting")
    assert store.activity_corrections("2026-09-06") == {"Thing": "distracting"}


def test_bad_corrections_are_rejected(store):
    with pytest.raises(ValueError):
        store.correct_activity("2026-09-06", "Thing", "productive-ish")
    with pytest.raises(ValueError):
        store.correct_activity("2026-09-06", "   ", "aligned")


def test_correcting_a_day_by_hand_raises_confidence(store):
    plan = {"outcomes": "Study algorithms", "timeline": [block("LeetCode")]}
    rows = [sample("LeetCode", "study", "productive", 25), sample("Mystery", "other", "neutral", 25)]
    assert productivity_summary(rows, plan)["confidence"] == "low"
    assert productivity_summary(rows, plan, corrections={"Mystery": "aligned"})["confidence"] == "medium"


def test_evidence_rows_carry_a_readable_label(store):
    rows = [sample("DLS26 com.firsttouchgames.dls7", "other", "neutral", 10)]
    evidence = productivity_summary(rows, None)["evidence"][0]
    assert evidence["title"] == "DLS26 com.firsttouchgames.dls7"
    assert evidence["label"] == "DLS26"
    assert humanize_title("https://www.leetcode.com/problems/x") == "leetcode.com"
    assert humanize_title("") == "something"


def test_week_comparison_uses_goals_not_unlike_units(store):
    plan = store.save_plan("A\nB", [block()], day="2026-09-06")
    store.set_goal_status(plan["goals"][0]["id"], "done")
    stats = day_stats(store, "2026-09-06")
    assert stats["goals"] == 2
    assert stats["done"] == 1
    assert "events" not in stats and "blocks" not in stats


def test_recap_cards_walk_the_decision_loop(store):
    plan = store.save_plan("Ship it\nRead the paper", [block()], day="2026-09-06")
    store.set_goal_status(plan["goals"][0]["id"], "partial", note="half of it")
    cards = build_cards(store, "2026-09-06", phone_synced=True)

    kinds = [c.get("kind") for c in cards]
    assert "goals" in kinds and "evidence" in kinds and "lesson" in kinds and "tomorrow" in kinds
    for card in cards:
        if card.get("kind") in {"goals", "evidence", "lesson", "tomorrow"}:
            assert card["day"] == "2026-09-06"

    goals_card = next(c for c in cards if c.get("kind") == "goals")
    assert any("half of it" in line for line in goals_card["lines"])
    assert goals_card["stat"] == "1", "one goal still unjudged"

    tomorrow = next(c for c in cards if c.get("kind") == "tomorrow")
    assert tomorrow["stat"] == "2", "partial and unjudged goals both stay open"

    assert next(c for c in cards if c.get("kind") == "evidence")["stat_label"] == "estimated alignment"


def test_recap_of_an_unplanned_day_does_not_pretend(store):
    cards = build_cards(store, "2026-09-06", phone_synced=False)
    assert "did not plan" in cards[0]["body"]
    assert next(c for c in cards if c.get("kind") == "goals")["lines"] == []
    assert next(c for c in cards if c.get("kind") == "tomorrow")["stat"] == "0"


def test_reflection_api_round_trip(tmp_path):
    client = TestClient(create_app(str(tmp_path / "api.db")))
    client.post("/api/plan", json={"goals": [{"text": "Ship it"}], "timeline": [block()], "day": "2026-09-06"})

    assert client.post("/api/recap/reflect", json={"day": "2026-09-06", "lesson": "Start earlier."}).json()["lesson"] == "Start earlier."
    assert client.get("/api/recap/reflection?day=2026-09-06").json()["lesson"] == "Start earlier."

    corrected = client.post(
        "/api/activity/correct",
        json={"day": "2026-09-06", "title": "Recommended videos", "bucket": "aligned"},
    )
    assert corrected.status_code == 200
    assert client.post("/api/activity/correct", json={"day": "2026-09-06", "title": "x", "bucket": "nope"}).status_code == 400

    prod = client.get("/api/productivity?day=2026-09-06")
    assert prod.status_code == 200
    assert prod.json()["estimated"] is True
    assert client.get("/api/productivity?day=nonsense").status_code == 400


def test_today_names_the_day_the_recap_closes(tmp_path):
    client = TestClient(create_app(str(tmp_path / "api.db")))
    today = client.get("/api/today").json()
    assert today["recap_day"]
    assert today["recap_day"] <= today["day"]


def test_a_note_can_be_cleared_but_is_kept_when_absent(store):
    plan = store.save_plan("A", [block()], day="2026-09-06")
    goal_id = plan["goals"][0]["id"]
    assert store.set_goal_status(goal_id, "deferred", "ran out of time")["note"] == "ran out of time"
    assert store.set_goal_status(goal_id, "partial")["note"] == "ran out of time"
    assert store.set_goal_status(goal_id, "planned", "")["note"] is None
