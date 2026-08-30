from datetime import datetime, timezone

from timeless.classify_event import classify_event
from timeless.reminders import reminder_fires


def test_zoom_is_virtual_meeting():
    kind, modality = classify_event("Standup", "https://zoom.us/j/1", None)
    assert kind == "meeting"
    assert modality == "virtual"


def test_hackathon_physical_from_title_and_room():
    kind, modality = classify_event("UAPB Hackathon", None, "Campus Union Room 2")
    assert kind == "hackathon"
    assert modality == "physical"


def test_virtual_meeting_only_30m():
    start = datetime(2026, 8, 20, 18, 0, tzinfo=timezone.utc)
    fires = reminder_fires("meeting", "virtual", start)
    assert fires == [("start_30m", datetime(2026, 8, 20, 17, 30, tzinfo=timezone.utc))]


def test_hackathon_physical_includes_submit():
    start = datetime(2026, 8, 21, 16, 0, tzinfo=timezone.utc)
    submit = datetime(2026, 8, 22, 4, 0, tzinfo=timezone.utc)
    purposes = [p for p, _ in reminder_fires("hackathon", "physical", start, submit=submit)]
    assert purposes == ["start_1d", "start_2h", "submit_4h"]


def test_deadline_has_staged_followups():
    start = datetime(2026, 9, 20, 22, 0, tzinfo=timezone.utc)
    fires = reminder_fires("deadline", "virtual", start)
    assert [purpose for purpose, _ in fires] == ["deadline_7d", "deadline_1d", "deadline_4h"]


def test_course_has_short_reminder_and_calendar_note_has_none():
    start = datetime(2026, 9, 20, 15, 0, tzinfo=timezone.utc)
    assert reminder_fires("course", "physical", start) == [("course_15m", datetime(2026, 9, 20, 14, 45, tzinfo=timezone.utc))]
    assert reminder_fires("calendar_note", "physical", start) == []
