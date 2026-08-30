from datetime import datetime, timedelta, timezone

import pytest

from timeless.ingest import classify_screen_text, looks_like_job_url
from timeless.store import Store


@pytest.fixture
def store(tmp_path):
    s = Store(str(tmp_path / "t.db"))
    yield s
    s.close()


def test_empty_plan_rejected(store):
    with pytest.raises(ValueError):
        store.save_plan("", [{"task": "x", "start": "09:00", "end": "10:00"}])
    with pytest.raises(ValueError):
        store.save_plan("ship", [])


def test_plan_update_same_day(store):
    store.save_plan("a", [{"task": "one", "start": "09:00", "end": "10:00"}], day="2026-08-15")
    store.save_plan("b", [{"task": "two", "start": "10:00", "end": "11:00"}], day="2026-08-15")
    rows = store.conn.execute("SELECT COUNT(*) c FROM daily_plans").fetchone()
    assert rows["c"] == 1
    assert store.get_plan("2026-08-15")["outcomes"] == "b"


def test_app_settings_round_trip(store):
    assert store.get_setting("google_spreadsheet_id") is None
    store.set_setting("google_spreadsheet_id", "sheet-1")
    assert store.get_setting("google_spreadsheet_id") == "sheet-1"
    store.set_setting("google_spreadsheet_id", "sheet-2")
    assert store.get_setting("google_spreadsheet_id") == "sheet-2"
    store.delete_setting("google_spreadsheet_id")
    assert store.get_setting("google_spreadsheet_id") is None


def test_job_url_becomes_seen(store):
    out = store.ingest_url("https://boards.greenhouse.io/acme/jobs/123", "Intern")
    assert out["job"] is True
    assert out["opportunity"]["state"] == "seen"


def test_non_job_url_not_tracked(store):
    out = store.ingest_url("https://example.com/blog")
    assert out["job"] is False
    assert store.list_opportunities() == []
    assert store.conn.execute("SELECT COUNT(*) c FROM events").fetchone()["c"] == 0
    hearts = {h["sensor"]: h for h in store.heartbeats()}
    assert "mac_browser" in hearts


def test_phone_url_does_not_count_as_mac_browser(store):
    store.ingest_url("https://leetcode.com", title="LC", source="phone")
    hearts = {h["sensor"]: h for h in store.heartbeats()}
    assert "mac_browser" not in hearts
    assert "phone_aw" in hearts


def test_program_url_capture_is_selective_and_canonical(store):
    first = store.ingest_url("https://devpost.com/hackathons/ai?utm_source=email#top", "AI Hackathon")
    second = store.ingest_url("https://devpost.com/hackathons/ai?utm_medium=social", "AI Hackathon")
    assert first["tracked"] is True
    assert first["kind"] == "hackathon"
    assert second["opportunity"]["id"] == first["opportunity"]["id"]
    assert store.list_opportunities()[0]["url"] == "https://devpost.com/hackathons/ai"


def test_calendar_conference_is_promoted_to_tracker(store):
    store.upsert_meeting(
        "calendar-conf-1",
        "Data Science Conference",
        "2026-10-20T14:00:00Z",
        "2026-10-20T18:00:00Z",
        location="Convention Center",
        notes="Details https://example.org/data-conf",
    )
    opp = store.list_opportunities()[0]
    assert opp["kind"] == "conference"
    assert opp["url"] == "https://example.org/data-conf"
    assert opp["source"] == "calendar"


def test_opportunity_deadline_creates_reminders_but_not_checkin_halt(store):
    opp = store.upsert_opportunity(
        url="https://example.com/apply",
        role="Fellowship",
        deadline_at="2026-10-20",
    )
    uid = f"opportunity:{opp['id']}:deadline"
    purposes = {r["purpose"] for r in store.conn.execute("SELECT purpose FROM reminders WHERE event_uid=?", (uid,))}
    assert purposes == {"deadline_7d", "deadline_1d", "deadline_4h"}
    meeting = store.conn.execute("SELECT * FROM meetings WHERE uid=?", (uid,)).fetchone()
    assert meeting["reminder_only"] == 1
    at_deadline = datetime.fromisoformat(meeting["start_at"].replace("Z", "+00:00"))
    halt = store.active_halt(at_deadline)
    assert halt["halt_kind"] == "reminder"
    assert halt["can_im_in"] is False


def test_tracker_dirty_clears_only_after_sheet_publish(store):
    store.upsert_opportunity(url="https://example.com/job", role="Intern")
    assert store.get_setting("google_tracker_dirty") == "1"


def test_confirmation_requires_approval(store):
    store.ingest_url("https://jobs.lever.co/acme/abc")
    out = store.ingest_screen_text("Thank you for applying to Acme", "https://jobs.lever.co/acme/abc")
    assert out["kind"] == "confirmation"
    opp = store.list_opportunities()[0]
    assert opp["state"] == "seen"
    store.decide_approval(out["approval"]["id"], True)
    assert store.list_opportunities()[0]["state"] == "applied"


def test_shortlisted_state_and_zoom_reminder(store):
    opp = store.upsert_opportunity(url="https://example.com/hack", role="UAPB Hack", kind="hackathon")
    store.set_opportunity_state(opp["id"], "shortlisted")
    assert store.list_opportunities()[0]["state"] == "shortlisted"
    start = datetime(2026, 8, 20, 18, 0, tzinfo=timezone.utc)
    end = datetime(2026, 8, 20, 19, 0, tzinfo=timezone.utc)
    store.upsert_meeting(
        "zoom-1",
        "Standup",
        start.strftime("%Y-%m-%dT%H:%M:%SZ"),
        end.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "https://zoom.us/j/9",
    )
    at = datetime(2026, 8, 20, 17, 40, tzinfo=timezone.utc)
    halt = store.active_halt(at)
    assert halt["halt_kind"] == "reminder"
    assert halt["purpose"] == "start_30m"


def test_hackathon_email_becomes_program_and_meeting(store):
    store.add_mail_action(
        "mid-hack",
        "gmail",
        "UAPB Hackathon August 22, 2026",
        "hackathon",
        "Submit by August 22, 2026",
    )
    opps = store.list_opportunities()
    assert any(o["kind"] == "hackathon" for o in opps)
    meetings = store.list_meetings()
    assert any(m["uid"] == "mail:mid-hack" for m in meetings)


def test_requirement_miss_asks(store):
    store.ingest_url("https://www.linkedin.com/jobs/view/1")
    out = store.ingest_screen_text("You must have 5 years of experience required", "https://www.linkedin.com/jobs/view/1")
    assert out["kind"] == "requirement_miss"
    assert store.list_opportunities()[0]["state"] == "seen"


def test_approval_expires_not_applied(store):
    store.ingest_url("https://ashbyhq.com/acme/job")
    out = store.ingest_screen_text("Application submitted", "https://ashbyhq.com/acme/job")
    past = datetime.now(timezone.utc) + timedelta(days=8)
    # backdate expiry
    store.conn.execute(
        "UPDATE pending_approvals SET expires_at=? WHERE id=?",
        ((datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ"), out["approval"]["id"]),
    )
    store.conn.commit()
    n = store.expire_approvals(past)
    assert n == 1
    assert store.list_opportunities()[0]["state"] == "seen"
    with pytest.raises(ValueError):
        store.decide_approval(out["approval"]["id"], True)


def test_mail_message_id_dedupe(store):
    a = store.add_mail_action("mid-1", "gmail", "Complete your application", "job", "finish it")
    b = store.add_mail_action("mid-1", "gmail", "Complete your application", "job", "finish it")
    assert a["id"] == b["id"]
    assert store.conn.execute("SELECT COUNT(*) c FROM mail_actions").fetchone()["c"] == 1


def test_mail_application_deadline_and_interview_create_correct_reminders(store):
    store.add_mail_action(
        "deadline-mail",
        "gmail",
        "Applications close September 20, 2026",
        "job",
        "Complete your application by September 20, 2026 https://jobs.lever.co/acme/1",
    )
    opp = next(o for o in store.list_opportunities() if "lever.co" in o["url"])
    assert opp["deadline_at"].startswith("2026-09-20")
    assert store.conn.execute("SELECT COUNT(*) c FROM reminders WHERE event_uid=?", (f"opportunity:{opp['id']}:deadline",)).fetchone()["c"] == 3

    store.add_mail_action(
        "interview-mail",
        "gmail",
        "Interview September 22, 2026",
        "interview",
        "Join September 22, 2026 at https://meet.google.com/abc-defg-hij",
    )
    meeting = store.conn.execute("SELECT * FROM meetings WHERE uid='mail:interview-mail'").fetchone()
    assert meeting["kind"] == "interview"
    assert meeting["join_url"] == "https://meet.google.com/abc-defg-hij"
    interview_opp = next(o for o in store.list_opportunities() if o["state"] == "interview")
    assert interview_opp["deadline_at"] is None


def test_meeting_ack_and_miss(store):
    start = datetime(2026, 8, 15, 10, 0, tzinfo=timezone.utc)
    end = datetime(2026, 8, 15, 11, 0, tzinfo=timezone.utc)
    m = store.upsert_meeting(
        "uid-1",
        "Standup",
        start.strftime("%Y-%m-%dT%H:%M:%SZ"),
        end.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "https://zoom.us/j/1",
    )
    mid = datetime(2026, 8, 15, 10, 5, tzinfo=timezone.utc)
    halt = store.active_halt(mid)
    assert halt["id"] == m["id"]
    store.ack_meeting(m["id"], "join")
    assert store.active_halt(mid) is None
    m2 = store.upsert_meeting(
        "uid-2",
        "Skip me",
        start.strftime("%Y-%m-%dT%H:%M:%SZ"),
        end.strftime("%Y-%m-%dT%H:%M:%SZ"),
        None,
    )
    after = datetime(2026, 8, 15, 12, 0, tzinfo=timezone.utc)
    store.close_elapsed_meetings(after)
    row = store.conn.execute("SELECT ack FROM meetings WHERE id=?", (m2["id"],)).fetchone()
    assert row["ack"] == "missed"


def test_confirming_day_ahead_reminder_consumes_it_without_headed(store):
    now = datetime.now(timezone.utc).replace(microsecond=0)
    start = now + timedelta(days=1) - timedelta(minutes=1)
    meeting = store.upsert_meeting(
        "physical-tomorrow",
        "Campus meeting",
        start.strftime("%Y-%m-%dT%H:%M:%SZ"),
        (start + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        location="Campus Union",
    )
    halt = store.due_reminder(now)
    assert halt["purpose"] == "start_1d"
    assert halt["can_headed"] is False
    assert halt["can_im_in"] is False
    store.ack_reminder(halt["id"], "confirm", "meeting", "physical")
    assert store.due_reminder(now) is None
    reminder = store.conn.execute("SELECT acked_at FROM reminders WHERE id=?", (halt["id"],)).fetchone()
    assert reminder["acked_at"] is not None
    with pytest.raises(ValueError, match="15 minutes"):
        store.ack_meeting(meeting["id"], "im_in", confirm=True)


def test_headed_only_on_two_hour_physical_reminder(store):
    now = datetime.now(timezone.utc).replace(microsecond=0)
    start = now + timedelta(hours=2) - timedelta(minutes=1)
    store.upsert_meeting(
        "physical-soon",
        "On-site interview",
        start.strftime("%Y-%m-%dT%H:%M:%SZ"),
        (start + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        location="Downtown office",
    )
    halt = store.due_reminder(now)
    assert halt["purpose"] == "start_2h"
    assert halt["can_headed"] is True
    assert halt["can_im_in"] is False


def test_changing_modality_removes_stale_reminders(store):
    meeting = store.upsert_meeting(
        "change-modality",
        "Planning session",
        "2026-10-20T18:00:00Z",
        "2026-10-20T19:00:00Z",
        location="Office",
    )
    purposes = {r["purpose"] for r in store.conn.execute("SELECT purpose FROM reminders WHERE event_uid=?", (meeting["uid"],))}
    assert purposes == {"start_1d", "start_2h"}
    store.patch_meeting(meeting["id"], modality="virtual")
    purposes = {r["purpose"] for r in store.conn.execute("SELECT purpose FROM reminders WHERE event_uid=?", (meeting["uid"],))}
    assert purposes == {"start_30m"}


def test_course_and_academic_markers_control_halts(store):
    course = store.upsert_meeting(
        "course-1",
        "CPSI 20193 · Computer Science II",
        "2026-10-20T14:00:00Z",
        "2026-10-20T14:50:00Z",
        location="STEM 103",
        notes="Timeless kind: course",
    )
    assert course["kind"] == "course"
    assert {r["purpose"] for r in store.conn.execute("SELECT purpose FROM reminders WHERE event_uid='course-1'")} == {"course_15m"}
    note = store.upsert_meeting(
        "academic-1",
        "UAPB · Fall Break",
        "2026-10-29T05:00:00Z",
        "2026-10-31T05:00:00Z",
        location="UAPB",
        notes="Timeless kind: calendar_note",
    )
    assert note["reminder_only"] == 1
    assert store.conn.execute("SELECT COUNT(*) c FROM reminders WHERE event_uid='academic-1'").fetchone()["c"] == 0


def test_ingest_picks_meet_from_notes_not_maps(store):
    m = store.upsert_meeting(
        "cal-1",
        "Standup",
        "2026-08-20T18:00:00Z",
        "2026-08-20T19:00:00Z",
        join_url="https://maps.google.com/?q=office",
        notes="Join: https://meet.google.com/abc-defg-hij maps https://maps.google.com/?q=1",
    )
    assert m["join_url"] == "https://meet.google.com/abc-defg-hij"


def test_mail_card_fills_empty_join(store):
    store.add_mail_action(
        "mid-meet",
        "gmail",
        "Acme Interview Loop",
        "interview",
        "https://zoom.us/j/555",
    )
    m = store.upsert_meeting(
        "cal-2",
        "Acme Interview Loop",
        "2026-08-21T18:00:00Z",
        "2026-08-21T19:00:00Z",
        join_url=None,
        notes="Bring resume",
    )
    assert m["join_url"] == "https://zoom.us/j/555"


def test_patched_join_not_overwritten(store):
    m = store.upsert_meeting(
        "cal-3",
        "Standup",
        "2026-08-20T18:00:00Z",
        "2026-08-20T19:00:00Z",
        notes="https://meet.google.com/old-link",
    )
    store.patch_meeting(m["id"], join_url="https://zoom.us/j/locked")
    again = store.upsert_meeting(
        "cal-3",
        "Standup",
        "2026-08-20T18:00:00Z",
        "2026-08-20T19:00:00Z",
        notes="https://meet.google.com/new-link",
    )
    assert again["join_url"] == "https://zoom.us/j/locked"
    assert again["join_locked"] == 1


def test_patch_opportunity_fields(store):
    o = store.upsert_opportunity(url="https://example.com/job", role="Intern")
    out = store.patch_opportunity(o["id"], role="SWE intern", kind="internship", url="https://example.com/job2")
    assert out["role"] == "SWE intern"
    assert out["url"] == "https://example.com/job2"


def test_ritual_done_praise(store):
    rid = store.add_ritual("LeetCode", launch_url="https://leetcode.com")
    out = store.complete_ritual(rid, day="2026-08-15")
    assert "LeetCode" in out["praise"]
    with pytest.raises(ValueError):
        store.complete_ritual(rid, day="2026-08-15")


def test_looks_like_job():
    assert looks_like_job_url("https://boards.greenhouse.io/x/jobs/1")
    assert not looks_like_job_url("https://news.ycombinator.com")
    assert classify_screen_text("Thank you for applying") == "confirmation"
