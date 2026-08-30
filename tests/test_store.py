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
    hearts = {h["sensor"]: h for h in store.heartbeats()}
    assert "mac_browser" in hearts


def test_phone_url_does_not_count_as_mac_browser(store):
    store.ingest_url("https://leetcode.com", title="LC", source="phone")
    hearts = {h["sensor"]: h for h in store.heartbeats()}
    assert "mac_browser" not in hearts
    assert "phone_aw" in hearts


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
