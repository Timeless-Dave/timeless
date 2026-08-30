from timeless.academics import current_semester, semester_events, semester_public


def test_fall_semester_courses_and_presets_are_clean():
    semester = current_semester("2026-09-01")
    assert semester["id"] == "uapb-fall-2026"
    public = semester_public(semester)
    assert len(public["courses"]) == 6
    assert "LeetCode" in public["presets"]
    assert "Calculus II" in public["presets"]


def test_semester_events_skip_holidays_and_mark_event_types():
    semester = current_semester("2026-09-01")
    events = semester_events(semester)
    assert any(event["title"].startswith("MATH 22095") and event["start_at"].startswith("2026-08-24") for event in events)
    assert not any(event["title"].startswith("MATH 22095") and event["start_at"].startswith("2026-09-07") for event in events)
    course = next(event for event in events if event["title"].startswith("CPSI 20193"))
    assert "Timeless kind: course" in course["notes"]
    deadline = next(event for event in events if "drop a class" in event["title"])
    assert deadline["all_day"] is True
    assert "Timeless kind: deadline" in deadline["notes"]
