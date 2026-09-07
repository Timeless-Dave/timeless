from datetime import datetime, timezone

from timeless.clock import day_key
from timeless.productivity import classify_activity, productivity_summary
from timeless.store import Store


def sample(category, productivity, minutes, title=""):
    return {
        "category": category,
        "productivity": productivity,
        "duration_seconds": minutes * 60,
        "title": title,
        "app": "",
        "host": "",
    }


def test_activity_classification_prefers_study_context():
    assert classify_activity("Chrome", "Python tutorial lecture", "youtube.com") == ("study", "productive")
    assert classify_activity("Chrome", "Recommended videos", "youtube.com") == ("distraction", "distracting")
    assert classify_activity("Code", "project.py", "") == ("development", "productive")
    assert classify_activity("Chrome", "News", "example.com") == ("other", "neutral")


def test_productivity_separates_alignment_off_plan_and_unknown():
    plan = {"outcomes": "Submit internship applications", "timeline": [{"task": "Apply to two internships"}]}
    result = productivity_summary(
        [
            sample("applications", "productive", 30, "Internship application"),
            sample("development", "productive", 20, "Side project coding"),
            sample("distraction", "distracting", 10, "Netflix"),
            sample("other", "neutral", 15, "Unknown activity"),
        ],
        plan,
    )
    assert result["minutes"] == {"aligned": 30, "productive_off_plan": 20, "distracting": 10, "unknown": 15}
    assert result["score"] == 68
    assert result["alignment"] == 60
    assert result["coverage"] == "medium"


def test_overlapping_window_and_web_samples_are_not_double_counted():
    plan = {"outcomes": "Study algorithms", "timeline": [{"task": "LeetCode"}]}
    rows = [
        {**sample("other", "neutral", 15, "Google Chrome"), "ts": "2026-08-30T15:00:00Z", "source_id": "window:1"},
        {**sample("study", "productive", 15, "LeetCode"), "ts": "2026-08-30T15:00:00Z", "source_id": "web:1", "host": "leetcode.com"},
    ]
    result = productivity_summary(rows, plan)
    assert result["tracked_minutes"] == 15
    assert result["minutes"]["aligned"] == 15


def test_activity_samples_dedupe_and_score_against_daily_plan(tmp_path):
    store = Store(str(tmp_path / "activity.db"))
    day = day_key()
    store.save_plan("Study algorithms", [{"task": "LeetCode", "start": "09:00", "end": "10:00"}], day=day)
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    payload = {
        "source": "mac_aw",
        "source_id": "bucket:123",
        "ts": timestamp,
        "duration_seconds": 600,
        "app": "Chrome",
        "host": "leetcode.com",
        "title": "Two Sum",
    }
    store.add_activity(**payload)
    payload["duration_seconds"] = 900
    store.add_activity(**payload)
    assert len(store.activities_on_day(day)) == 1
    result = store.productivity_on_day(day)
    assert result["minutes"]["aligned"] == 15
    assert result["score"] == 100
    store.close()


def test_summary_publishes_the_score_denominator_and_confidence():
    plan = {"outcomes": "Study algorithms", "timeline": [{"task": "LeetCode"}]}
    result = productivity_summary(
        [
            sample("study", "productive", 25, "LeetCode algorithms"),
            sample("other", "neutral", 5, "Unknown activity"),
        ],
        plan,
    )
    # The score judges 25 minutes, not the 30 that were tracked.
    assert result["tracked_minutes"] == 30
    assert result["judged_minutes"] == 25
    assert result["unknown_share"] == round(5 / 30, 3)
    assert result["confidence"] == "medium"
    assert result["estimated"] is True


def test_confidence_drops_when_evidence_is_thin_or_mostly_unclassified():
    plan = {"outcomes": "Study algorithms", "timeline": [{"task": "LeetCode"}]}
    thin = productivity_summary([sample("study", "productive", 10, "LeetCode")], plan)
    assert thin["confidence"] == "low"

    murky = productivity_summary(
        [sample("study", "productive", 60, "LeetCode"), sample("other", "neutral", 90, "Unknown")],
        plan,
    )
    assert murky["confidence"] == "low"

    unplanned = productivity_summary([sample("study", "productive", 200, "LeetCode")], None)
    assert unplanned["confidence"] == "low"


def test_summary_reports_when_the_last_sample_landed():
    rows = [
        {**sample("study", "productive", 10, "LeetCode"), "ts": "2026-08-30T15:00:00Z"},
        {**sample("study", "productive", 10, "LeetCode"), "ts": "2026-08-30T16:00:00Z"},
    ]
    assert productivity_summary(rows, None)["last_sample_at"] == "2026-08-30T16:00:00Z"
    assert productivity_summary([], None)["last_sample_at"] is None
