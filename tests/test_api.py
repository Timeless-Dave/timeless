from datetime import datetime, timedelta

from fastapi.testclient import TestClient

from timeless.app import create_app


def client(tmp_path):
    app = create_app(str(tmp_path / "api.db"))
    return TestClient(app)


def test_access_lists_urls_on_loopback(tmp_path):
    c = client(tmp_path)
    r = c.get("/api/access")
    assert r.status_code == 200
    assert r.json()["loopback"] is True
    assert any("127.0.0.1" in u for u in r.json()["urls"])


def test_today_does_not_generate_recap_or_pull_phone(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "timeless.app.ensure_recap",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("today must not generate recap")),
    )
    c = client(tmp_path)
    t = c.get("/api/today").json()
    assert t["needs_recap"] is True
    assert t["recap"] is None


def test_skip_phone_generates_mac_only_recap(monkeypatch, tmp_path):
    monkeypatch.setattr("timeless.recap.pull_phone", lambda *a, **k: (_ for _ in ()).throw(AssertionError("skip")))
    c = client(tmp_path)
    r = c.post("/api/recap/generate", json={"skip_phone": True})
    assert r.status_code == 200
    body = r.json()
    assert body["phone_synced"] is False
    assert body["cards"]
    t = c.get("/api/today").json()
    assert t["recap"]["phone_synced"] is False
    ack = c.post("/api/recap/ack")
    assert ack.status_code == 200
    assert c.get("/api/today").json()["needs_recap"] is False


def test_today_uses_chicago_and_can_ack_recap(tmp_path):
    c = client(tmp_path)
    t = c.get("/api/today").json()
    assert t["tz"] == "America/Chicago"
    assert "heatmap" in t
    assert t["needs_recap"] is True
    assert t["needs_gate"] is True
    assert t["brain"] == "online"
    c.post("/api/recap/generate", json={"skip_phone": True})
    ack = c.post("/api/recap/ack")
    assert ack.status_code == 200
    later = c.get("/api/today").json()
    assert later["needs_recap"] is False
    assert later["needs_gate"] is True


def test_plan_and_gate(tmp_path):
    c = client(tmp_path)
    bad = c.post("/api/plan", json={"outcomes": "", "timeline": [{"task": "x"}]})
    assert bad.status_code in (400, 422)
    ok = c.post(
        "/api/plan",
        json={
            "outcomes": "Ship Timeless brain",
            "timeline": [
                {"start": "21:00", "end": "22:00", "task": "LeetCode", "ritual": "leetcode"}
            ],
        },
    )
    assert ok.status_code == 200
    assert c.get("/api/today").json()["needs_gate"] is False


def test_plan_for_future_day(tmp_path):
    c = client(tmp_path)
    today = c.get("/api/today").json()["day"]
    nxt = (datetime.strptime(today, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
    r = c.post(
        "/api/plan",
        json={
            "outcomes": "Prep tomorrow",
            "timeline": [{"task": "read", "start": "09:00", "end": "10:00"}],
            "day": nxt,
        },
    )
    assert r.status_code == 200
    assert c.get("/api/today").json()["needs_gate"] is True
    got = c.get("/api/plan", params={"day": nxt}).json()
    assert got["outcomes"] == "Prep tomorrow"
    assert c.get("/api/plan", params={"day": "nope"}).status_code == 400


def test_manual_program_tracking(tmp_path):
    c = client(tmp_path)
    bad = c.post("/api/opportunities", json={"role": "Intern", "url": "not-a-url"})
    assert bad.status_code == 400
    made = c.post("/api/opportunities", json={
        "company": "Acme",
        "role": "Software Intern",
        "kind": "internship",
        "state": "seen",
        "deadline_at": "2026-09-10",
        "url": "https://example.com/jobs/1",
    })
    assert made.status_code == 200
    opp = made.json()
    changed = c.patch(f"/api/opportunities/{opp['id']}", json={"company": "Acme Labs", "deadline_at": "2026-09-12"})
    assert changed.json()["company"] == "Acme Labs"
    assert changed.json()["deadline_at"] == "2026-09-12"


def test_chat_accepts_history(tmp_path):
    c = client(tmp_path)
    c.post("/api/plan", json={"outcomes": "work", "timeline": [{"task": "code", "start": "9", "end": "10"}]})
    r = c.post(
        "/api/chat",
        json={
            "message": "and after that?",
            "history": [
                {"role": "user", "content": "what is my plan"},
                {"role": "assistant", "content": "Ship the gate."},
            ],
        },
    )
    assert r.status_code == 200
    assert "reply" in r.json()


def test_chat_offline_does_not_500(tmp_path):
    c = client(tmp_path)
    c.post("/api/plan", json={"outcomes": "work", "timeline": [{"task": "code", "start": "9", "end": "10"}]})
    r = c.post("/api/chat", json={"message": "what did I do"})
    assert r.status_code == 200
    assert "offline" in r.json()


def test_meeting_ack_api(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "timeless.hands.run",
        lambda intent: {"did": "open_url", "url": intent["url"], "target": intent["target"]},
    )
    c = client(tmp_path)
    m = c.post(
        "/api/meetings",
        json={
            "uid": "m1",
            "title": "Interview",
            "start_at": "2020-01-01T00:00:00Z",
            "end_at": "2099-01-01T00:00:00Z",
            "join_url": "https://meet.google.com/abc",
        },
    ).json()
    halt = c.get("/api/today").json()["halt"]
    assert halt["id"] == m["id"]
    assert halt["requires_join"] is True
    assert halt["can_im_in"] is False
    bad = c.post(f"/api/meetings/{m['id']}/ack", json={"action": "im_in", "confirm": True})
    assert bad.status_code == 400
    c.post(f"/api/meetings/{m['id']}/join")
    assert c.get("/api/today").json()["halt"] is None


def test_im_in_requires_confirm(tmp_path):
    c = client(tmp_path)
    m = c.post(
        "/api/meetings",
        json={
            "uid": "phys-1",
            "title": "On site",
            "start_at": "2020-01-01T00:00:00Z",
            "end_at": "2099-01-01T00:00:00Z",
            "join_url": None,
        },
    ).json()
    c.patch(f"/api/meetings/{m['id']}", json={"modality": "physical"})
    halt = c.get("/api/today").json()["halt"]
    assert halt["can_im_in"] is True
    r = c.post(f"/api/meetings/{m['id']}/ack", json={"action": "im_in"})
    assert r.status_code == 400
    c.post(f"/api/meetings/{m['id']}/ack", json={"action": "im_in", "confirm": True})
    assert c.get("/api/today").json()["halt"] is None


def test_heartbeat_api(tmp_path):
    c = client(tmp_path)
    r = c.post("/api/heartbeat", json={"sensor": "mac_aw", "detail": "ok"})
    assert r.status_code == 200
    sensors = [h["sensor"] for h in c.get("/api/today").json()["heartbeats"]]
    assert "mac_aw" in sensors


def test_activity_api_returns_classification(tmp_path):
    c = client(tmp_path)
    result = c.post("/api/activity", json={
        "source": "mac_aw",
        "source_id": "event-1",
        "ts": "2026-08-30T15:00:00Z",
        "duration_seconds": 300,
        "app": "Chrome",
        "host": "leetcode.com",
        "title": "Dynamic programming practice",
    })
    assert result.status_code == 200
    assert result.json()["category"] == "study"
    assert result.json()["productivity"] == "productive"


def test_academic_routes_expose_courses_and_sync_calendar(monkeypatch, tmp_path):
    monkeypatch.setattr("timeless.app.sync_calendar_events", lambda events: {"ok": True, "created": len(events), "updated": 0, "total": len(events)})
    c = client(tmp_path)
    academic = c.get("/api/academics/current")
    assert academic.status_code == 200
    assert len(academic.json()["courses"]) == 6
    synced = c.post("/api/academics/calendar/sync")
    assert synced.status_code == 200
    assert synced.json()["total"] > 100


def test_do_open_does_not_send(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "timeless.app.run_hands",
        lambda intent: {"did": "open_url", "url": intent["url"], "target": intent["target"]},
    )
    c = client(tmp_path)
    r = c.post("/api/do", json={"message": "open leetcode"})
    assert r.status_code == 200
    body = r.json()
    assert body["did"]["url"] == "https://leetcode.com"
    assert "Opened leetcode" in body["reply"]


def test_patch_meeting_locks_join(tmp_path):
    c = client(tmp_path)
    m = c.post(
        "/api/meetings",
        json={
            "uid": "m-lock",
            "title": "Standup",
            "start_at": "2026-08-20T18:00:00Z",
            "end_at": "2026-08-20T19:00:00Z",
            "notes": "https://maps.google.com/?q=x https://meet.google.com/abc",
        },
    ).json()
    assert m["join_url"] == "https://meet.google.com/abc"
    patched = c.patch(f"/api/meetings/{m['id']}", json={"join_url": "https://zoom.us/j/9"}).json()
    assert patched["join_url"] == "https://zoom.us/j/9"
    assert patched["join_locked"] == 1


def test_chat_add_event_upserts(monkeypatch, tmp_path):
    monkeypatch.setattr("timeless.app.create_calendar_event", lambda **kw: {"ok": False, "error": "test skip EventKit"})
    c = client(tmp_path)
    r = c.post(
        "/api/chat",
        json={"message": "add event Interview 2026-08-20 14:00-15:00 https://meet.google.com/xyz"},
    )
    assert r.status_code == 200
    body = r.json()
    assert "Interview" in body["reply"]
    meetings = c.get("/api/today").json()["meetings"]
    assert any(m["title"] == "Interview" and m["join_url"] == "https://meet.google.com/xyz" for m in meetings)


def test_chat_queues_send_instead_of_sending(tmp_path):
    c = client(tmp_path)
    r = c.post("/api/chat", json={"message": "send a text to mom"})
    assert r.status_code == 200
    body = r.json()
    assert body["did"] is None
    assert "will not send" in body["reply"].lower()
    kinds = [a["kind"] for a in c.get("/api/today").json()["approvals"]]
    assert "do_send" in kinds


def test_meeting_join_api(monkeypatch, tmp_path):
    opened = []
    monkeypatch.setattr(
        "timeless.hands.run",
        lambda intent: opened.append(intent) or {"did": "open_url", "url": intent["url"], "target": "mac"},
    )
    c = client(tmp_path)
    m = c.post(
        "/api/meetings",
        json={
            "uid": "join-1",
            "title": "Standup",
            "start_at": "2020-01-01T00:00:00Z",
            "end_at": "2099-01-01T00:00:00Z",
            "join_url": "https://meet.google.com/abc-defg-hij",
        },
    ).json()
    r = c.post(f"/api/meetings/{m['id']}/join")
    assert r.status_code == 200
    assert r.json()["url"] == "https://meet.google.com/abc-defg-hij"
    assert opened[0]["url"] == "https://meet.google.com/abc-defg-hij"
    assert c.get("/api/today").json()["halt"] is None


def test_meeting_join_cleans_messy_teams_url(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "timeless.hands.run",
        lambda intent: {"did": "open_url", "url": intent["url"], "target": "mac"},
    )
    c = client(tmp_path)
    dirty = "https://teams.microsoft.com/meet/123?p=abc<https://safelinks.example.com/foo"
    m = c.post(
        "/api/meetings",
        json={
            "uid": "teams-1",
            "title": "Teams call",
            "start_at": "2020-01-01T00:00:00Z",
            "end_at": "2099-01-01T00:00:00Z",
            "join_url": dirty,
        },
    ).json()
    halt = c.get("/api/today").json()["halt"]
    assert halt["join_url"] == "https://teams.microsoft.com/meet/123?p=abc"
    r = c.post(f"/api/meetings/{m['id']}/join")
    assert r.status_code == 200
    assert r.json()["url"] == "https://teams.microsoft.com/meet/123?p=abc"


def test_accept_mark_applied_missing_opportunity_returns_400(tmp_path):
    c = client(tmp_path)
    app = create_app(str(tmp_path / "api.db"))
    store = app.state.store
    approval = store.propose("mark_applied", {"opportunity_id": None, "url": None, "snippet": "inbox noise"})
    r = c.post(f"/api/approvals/{approval['id']}/accept")
    assert r.status_code == 400
    assert "posting" in r.json()["detail"].lower()


def test_quiet_api(tmp_path):
    c = client(tmp_path)
    m = c.post(
        "/api/meetings",
        json={
            "uid": "q1",
            "title": "Standup",
            "start_at": "2020-01-01T00:00:00Z",
            "end_at": "2099-01-01T00:00:00Z",
        },
    ).json()
    assert c.get("/api/today").json()["halt"]["id"] == m["id"]
    q = c.post("/api/quiet", json={"level": "quiet", "minutes": 30}).json()
    assert q["level"] == "quiet"
    today = c.get("/api/today").json()
    assert today["halt"] is None
    assert today["quiet"]["level"] == "quiet"
    assert today["muted_halt"]["title"] == "Standup"
    c.delete(f"/api/quiet/{q['id']}")
    assert c.get("/api/today").json()["halt"]["id"] == m["id"]


def test_panic_quiet_api(tmp_path):
    c = client(tmp_path)
    r = c.post("/api/quiet/panic")
    assert r.status_code == 200
    assert r.json()["level"] == "dormant"
    assert r.json()["reason"] == "panic"
