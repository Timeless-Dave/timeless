from __future__ import annotations

import json
import os
import re
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from timeless.access import advertised_hosts, is_loopback, token_ok, ui_token
from timeless.academics import current_semester, semester_events, semester_public
from timeless.calendar_write import create_calendar_event, sync_calendar_events
from timeless.clock import day_key, due_recap_day, zone
from timeless.hands import parse, run as run_hands
from timeless.google_sheets import GoogleSheets, GoogleSheetsError
from timeless.local_cmd import apply_local, parse_local
from timeless.recap import build_cards, connect_phone, ensure_recap
from timeless.store import Store

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "web"
FRONTEND_DIST = ROOT / "frontend" / "dist"
DEFAULT_DB = Path.home() / "Library" / "Application Support" / "Timeless" / "timeless.db"


class PlanIn(BaseModel):
    outcomes: str
    timeline: list[dict] = Field(min_length=1)
    day: str | None = None


class RitualIn(BaseModel):
    name: str
    launch_url: str | None = None
    app_bundle: str | None = None
    weekdays: str = "1,2,3,4,5"
    match_host: str | None = None
    min_minutes: int | None = None


class MeetingIn(BaseModel):
    uid: str
    title: str
    start_at: str
    end_at: str
    join_url: str | None = None
    location: str | None = None
    notes: str | None = None


class ReminderAckIn(BaseModel):
    action: str
    kind: str | None = None
    modality: str | None = None


class MeetingPatchIn(BaseModel):
    join_url: str | None = None
    modality: str | None = None
    kind: str | None = None
    title: str | None = None


class OppPatchIn(BaseModel):
    company: str | None = None
    role: str | None = None
    kind: str | None = None
    url: str | None = None
    deadline_at: str | None = None


class OppIn(BaseModel):
    company: str | None = None
    role: str
    kind: str = "internship"
    state: str = "seen"
    url: str
    deadline_at: str | None = None


class OppStateIn(BaseModel):
    state: str
    kind: str | None = None


class AckIn(BaseModel):
    action: str
    confirm: bool = False


class JoinIn(BaseModel):
    reminder_id: int | None = None


class UrlIn(BaseModel):
    url: str
    title: str | None = None
    source: str | None = None


class ScreenIn(BaseModel):
    text: str
    url: str | None = None


class PhoneIn(BaseModel):
    summary: str
    payload: dict | None = None


class MailIn(BaseModel):
    message_id: str
    account: str
    subject: str
    classification: str
    card: str


class RecapGenIn(BaseModel):
    skip_phone: bool = False
    mode: str | None = None


class PhoneConnectIn(BaseModel):
    mode: str = "wireless"


class ChatTurn(BaseModel):
    role: str
    content: str


class ChatIn(BaseModel):
    message: str
    history: list[ChatTurn] = []


class HeartbeatIn(BaseModel):
    sensor: str
    detail: str | None = None


class ActivityIn(BaseModel):
    source: str
    source_id: str
    ts: str
    duration_seconds: float = Field(ge=0, le=86400)
    app: str | None = None
    host: str | None = None
    title: str | None = None


class QuietIn(BaseModel):
    level: str = "quiet"
    minutes: int | None = 60
    ends_at: str | None = None
    reason: str | None = None


def create_app(db_path: str | None = None) -> FastAPI:
    db_path = db_path or os.environ.get("TIMELESS_DB", str(DEFAULT_DB))
    store = Store(db_path)
    app = FastAPI(title="Timeless")
    app.state.store = store
    google = GoogleSheets(store)
    app.state.google_sheets = google

    @app.middleware("http")
    async def require_token(request: Request, call_next):
        # Browsers do not copy the page's token query string to CSS, script, or
        # font requests. These files contain no personal data, so serve them
        # without authentication while keeping pages and APIs protected.
        if request.url.path.startswith("/static/") or request.url.path.startswith("/assets/") or request.url.path.startswith("/fonts/"):
            return await call_next(request)
        host = request.client.host if request.client else ""
        provided = request.headers.get("authorization") or ""
        if provided.lower().startswith("bearer "):
            provided = provided[7:].strip()
        else:
            provided = request.query_params.get("token")
        if not token_ok(provided, host):
            return JSONResponse({"detail": "token required"}, status_code=401)
        return await call_next(request)

    @app.get("/api/access")
    def access(request: Request):
        host = request.client.host if request.client else ""
        port = int(os.environ.get("TIMELESS_PORT", "8787"))
        token = ui_token() if is_loopback(host) else None
        urls = []
        if token:
            for h in advertised_hosts():
                urls.append(f"http://{h}:{port}/?token={token}")
        return {"loopback": is_loopback(host), "urls": urls, "tz": str(zone())}

    @app.get("/api/today")
    def today():
        store.close_elapsed_meetings()
        store.expire_approvals()
        now_day = day_key()
        recap = store.get_recap(due_recap_day())
        plan = store.get_plan(now_day)
        quiet = store.quiet_summary()
        halt = store.active_halt()
        muted = None
        if quiet and quiet.get("level") in {"quiet", "dormant"}:
            raw = store._raw_active_halt()
            if raw:
                muted = {"title": raw.get("title"), "halt_kind": raw.get("halt_kind")}
        return {
            "plan": plan,
            "day": now_day,
            "tz": str(zone()),
            "needs_gate": plan is None,
            "needs_recap": store.needs_recap(),
            "recap": recap,
            "halt": halt,
            "quiet": quiet,
            "muted_halt": muted,
            "opportunities": store.list_opportunities(),
            "approvals": store.list_approvals(),
            "rituals": store.list_rituals(),
            "meetings": store.list_meetings(),
            "mail": store.list_mail_actions(),
            "heartbeats": store.heartbeats(),
            "heatmap": store.heatmap(),
            "productivity": store.productivity_on_day(now_day),
            "brain": "online",
        }

    @app.get("/api/integrations/google")
    def google_status():
        return google.status()

    @app.post("/api/integrations/google/connect")
    def google_connect(request: Request):
        host = request.client.host if request.client else ""
        if not is_loopback(host):
            raise HTTPException(403, "Connect Google Sheets from the Mac running Timeless")
        try:
            return {"authorization_url": google.authorization_url()}
        except GoogleSheetsError as exc:
            raise HTTPException(400, str(exc)) from exc

    @app.get("/api/academics/current")
    def academics_current():
        semester = current_semester()
        return semester_public(semester) if semester else {"courses": [], "academic_dates": [], "presets": []}

    @app.post("/api/academics/calendar/sync")
    def academics_calendar_sync(request: Request):
        host = request.client.host if request.client else ""
        if not is_loopback(host):
            raise HTTPException(403, "Sync the academic calendar from the Mac running Timeless")
        semester = current_semester()
        if not semester:
            raise HTTPException(404, "No semester configuration found")
        result = sync_calendar_events(semester_events(semester))
        if not result.get("ok"):
            raise HTTPException(400, result.get("error") or "Calendar sync failed")
        return {**result, "semester": semester.get("name")}

    @app.get("/oauth/google/callback")
    def google_callback(code: str | None = None, state: str | None = None, error: str | None = None):
        if error:
            return RedirectResponse(url="/?google=denied#panel-programs", status_code=303)
        if not code or not state:
            raise HTTPException(400, "Google callback is missing code or state")
        try:
            google.complete_authorization(code, state)
        except GoogleSheetsError as exc:
            raise HTTPException(400, str(exc)) from exc
        return RedirectResponse(url="/?google=connected#panel-programs", status_code=303)

    @app.post("/api/integrations/google/sync")
    def google_sync():
        try:
            return google.publish(store.list_opportunities())
        except GoogleSheetsError as exc:
            raise HTTPException(409 if "already running" in str(exc) else 400, str(exc)) from exc

    @app.delete("/api/integrations/google")
    def google_disconnect():
        try:
            google.disconnect()
            return google.status()
        except GoogleSheetsError as exc:
            raise HTTPException(400, str(exc)) from exc

    @app.post("/api/recap/ack")
    def recap_ack():
        try:
            return store.ack_recap()
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc

    @app.post("/api/recap/generate")
    def recap_generate(body: RecapGenIn):
        if body.skip_phone:
            return ensure_recap(store, do_pull=False)
        linked = connect_phone(body.mode or "wireless")
        out = ensure_recap(store, do_pull=False)
        if linked.get("ok"):
            day = due_recap_day()
            cards = build_cards(store, day, True)
            out = store.save_recap(day, cards, True)
        out = dict(out)
        out["phone"] = linked
        return out

    @app.post("/api/phone/connect")
    def phone_connect(body: PhoneConnectIn):
        return connect_phone(body.mode)

    @app.get("/api/quiet")
    def list_quiet():
        return {"active": store.active_quiet(), "periods": store.list_quiet()}

    @app.post("/api/quiet")
    def create_quiet(body: QuietIn):
        try:
            return store.create_quiet(
                level=body.level,
                minutes=body.minutes,
                ends_at=body.ends_at,
                reason=body.reason,
                source="manual",
            )
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc

    @app.delete("/api/quiet/{quiet_id}")
    def end_quiet(quiet_id: int):
        try:
            return store.end_quiet(quiet_id)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc

    @app.post("/api/quiet/panic")
    def panic_quiet():
        return store.panic_quiet()

    @app.get("/api/plan")
    def get_plan(day: str | None = None):
        key = day or day_key()
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", key):
            raise HTTPException(400, "day must be YYYY-MM-DD")
        plan = store.get_plan(key)
        return plan or {"day": key, "outcomes": "", "timeline": []}

    @app.post("/api/plan")
    def save_plan(body: PlanIn):
        try:
            day = body.day or day_key()
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", day):
                raise ValueError("day must be YYYY-MM-DD")
            return store.save_plan(body.outcomes, body.timeline, day=day)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc

    @app.post("/api/rituals")
    def add_ritual(body: RitualIn):
        rid = store.add_ritual(**body.model_dump())
        return {"id": rid}

    @app.post("/api/rituals/{ritual_id}/done")
    def ritual_done(ritual_id: int):
        try:
            return store.complete_ritual(ritual_id)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc

    @app.post("/api/meetings")
    def add_meeting(body: MeetingIn):
        return store.upsert_meeting(**body.model_dump())

    @app.patch("/api/meetings/{meeting_id}")
    def patch_meeting(meeting_id: int, body: MeetingPatchIn):
        try:
            return store.patch_meeting(meeting_id, **body.model_dump())
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc

    @app.patch("/api/opportunities/{opp_id}")
    def patch_opp(opp_id: int, body: OppPatchIn):
        try:
            return store.patch_opportunity(opp_id, **body.model_dump())
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc

    @app.post("/api/opportunities")
    def add_opp(body: OppIn):
        if not body.url.startswith(("http://", "https://")):
            raise HTTPException(400, "URL must start with http:// or https://")
        try:
            return store.upsert_opportunity(**body.model_dump(), source="manual")
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc

    @app.post("/api/reminders/{reminder_id}/ack")
    def reminder_ack(reminder_id: int, body: ReminderAckIn):
        try:
            return store.ack_reminder(reminder_id, body.action, body.kind, body.modality)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc

    @app.post("/api/opportunities/{opp_id}/state")
    def opp_state(opp_id: int, body: OppStateIn):
        try:
            return store.set_opportunity_state(opp_id, body.state, body.kind)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc

    @app.post("/api/meetings/{meeting_id}/ack")
    def ack(meeting_id: int, body: AckIn):
        try:
            return store.ack_meeting(meeting_id, body.action, confirm=body.confirm)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc

    @app.post("/api/meetings/{meeting_id}/join")
    def meeting_join(meeting_id: int, body: JoinIn | None = None):
        try:
            reminder_id = body.reminder_id if body else None
            return store.join_meeting(meeting_id, reminder_id=reminder_id)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc

    @app.post("/api/ingest/url")
    def ingest_url(body: UrlIn):
        return store.ingest_url(body.url, body.title, source=body.source or "url")

    @app.post("/api/ingest/screen")
    def ingest_screen(body: ScreenIn):
        return store.ingest_screen_text(body.text, body.url)

    @app.post("/api/ingest/phone")
    def ingest_phone(body: PhoneIn):
        eid = store.ingest_phone(body.summary, body.payload)
        return {"id": eid}

    @app.post("/api/heartbeat")
    def heartbeat(body: HeartbeatIn):
        store.heartbeat(body.sensor, body.detail)
        return {"ok": True}

    @app.post("/api/activity")
    def activity(body: ActivityIn):
        try:
            return store.add_activity(**body.model_dump())
        except ValueError as exc:
            raise HTTPException(400, "invalid activity timestamp") from exc

    @app.post("/api/mail")
    def mail(body: MailIn):
        return store.add_mail_action(**body.model_dump())

    @app.post("/api/approvals/{approval_id}/accept")
    def accept(approval_id: int):
        try:
            return store.decide_approval(approval_id, True)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc

    @app.post("/api/approvals/{approval_id}/reject")
    def reject(approval_id: int):
        try:
            return store.decide_approval(approval_id, False)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc

    @app.post("/api/approvals/{approval_id}/keep")
    def keep(approval_id: int):
        try:
            approval = store.get_approval(approval_id)
            payload = approval["payload"]
            if payload.get("opportunity_id"):
                store.set_opportunity_state(int(payload["opportunity_id"]), "seen")
            return store.decide_approval(approval_id, False)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc

    @app.post("/api/do")
    def do_command(body: ChatIn):
        out = _maybe_do(store, body.message)
        if not out:
            raise HTTPException(400, "not an action I can run yet")
        return out

    @app.post("/api/chat")
    def chat(body: ChatIn):
        acted = _maybe_do(store, body.message)
        if acted:
            return {**acted, "offline": False}
        snapshot = today()
        ollama = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
        model = os.environ.get("OLLAMA_MODEL", "qwen2.5:7b")
        context = json.dumps(
            {
                "plan": snapshot["plan"],
                "opportunities": snapshot["opportunities"][:20],
                "mail": snapshot["mail"][:20],
                "approvals": snapshot["approvals"],
                "meetings": snapshot["meetings"][:10],
                "productivity": snapshot["productivity"],
            },
            default=str,
        )[:8000]
        system = (
            "You are Timeless, a local personal assistant talking with David. "
            "Be conversational and brief. Use the JSON snapshot. "
            "You can remind them they can type commands like: open leetcode, "
            "add event Interview 2026-08-20 14:00-15:00 https://meet.google.com/…, "
            "plan outcomes: …, mark Intern applied. You cannot send messages or email."
        )
        messages = [{"role": "system", "content": system + "\nSnapshot:\n" + context}]
        for turn in body.history[-12:]:
            role = turn.role if turn.role in {"user", "assistant"} else "user"
            content = (turn.content or "").strip()
            if content:
                messages.append({"role": role, "content": content})
        messages.append({"role": "user", "content": body.message})
        try:
            r = httpx.post(
                f"{ollama}/api/chat",
                json={"model": model, "messages": messages, "stream": False},
                timeout=60,
            )
            r.raise_for_status()
            data = r.json()
            reply = (data.get("message") or {}).get("content") or data.get("response") or ""
            return {"reply": reply.strip(), "offline": False}
        except Exception:
            return {
                "reply": _offline_chat(body.message, snapshot),
                "offline": True,
            }

    legacy_pages = {
        "/gate": WEB / "gate.html",
        "/halt": WEB / "halt.html",
        "/recap": WEB / "recap.html",
    }

    if WEB.exists() or FRONTEND_DIST.exists():

        def _spa_page(path: str):
            if FRONTEND_DIST.exists():
                return FileResponse(FRONTEND_DIST / "index.html")
            if path == "/":
                return FileResponse(WEB / "index.html")
            legacy = legacy_pages.get(path)
            if legacy and legacy.exists():
                return FileResponse(legacy)
            return FileResponse(WEB / "index.html")

        @app.get("/")
        def index():
            return _spa_page("/")

        @app.get("/gate")
        def gate():
            return _spa_page("/gate")

        @app.get("/halt")
        def halt():
            return _spa_page("/halt")

        @app.get("/recap")
        def recap_page():
            return _spa_page("/recap")

        if FRONTEND_DIST.exists():
            assets_dir = FRONTEND_DIST / "assets"
            if assets_dir.exists():
                app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")
            app.mount("/static", StaticFiles(directory=WEB), name="static")
            app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=False), name="spa-root")
        else:
            app.mount("/static", StaticFiles(directory=WEB), name="static")

    return app


def _maybe_do(store: Store, message: str) -> dict | None:
    halt = store.active_halt()
    if halt and re.search(r"\bjoin\b", message, re.I) and halt.get("join_url"):
        intent = {"action": "open_url", "target": "mac", "url": halt["join_url"], "label": halt["title"], "risky": False}
        did = run_hands(intent)
        store.ack_meeting(halt["id"], "join")
        return {"reply": f"Joining {halt['title']}.", "did": did}
    local = parse_local(message)
    if local:
        try:
            return apply_local(store, local, create_calendar_event)
        except ValueError as exc:
            return {"reply": str(exc), "did": None}
    intent = parse(message, store.list_rituals())
    if not intent:
        return None
    if intent.get("risky"):
        approval = store.propose("do_send", intent)
        return {
            "reply": f"I will not send or submit until you accept approval #{approval['id']}.",
            "did": None,
            "approval": approval,
        }
    try:
        did = run_hands(intent)
    except Exception as exc:
        return {"reply": f"Could not do that: {exc}", "did": None}
    where = intent.get("target") or "mac"
    return {"reply": f"Opened {intent.get('label')} on {where}.", "did": did}


def _offline_chat(message: str, snapshot: dict) -> str:
    msg = message.lower()
    opps = snapshot["opportunities"]
    if any(word in msg for word in ("productive", "productivity", "aligned", "alignment", "focus")):
        p = snapshot.get("productivity") or {}
        if p.get("score") is None:
            return "I do not have enough classified activity yet to estimate productivity. Keep ActivityWatch running."
        mins = p.get("minutes") or {}
        return (
            f"Estimated productivity is {p['score']} with {p.get('coverage', 'low')} coverage. "
            f"{mins.get('aligned', 0)}m matched the plan, {mins.get('productive_off_plan', 0)}m was productive but off-plan, "
            f"and {mins.get('distracting', 0)}m looked distracting."
        )
    if "didn" in msg and "apply" in msg or "opened" in msg:
        seen = [o for o in snapshot["opportunities"] if o["state"] == "seen"]
        if not seen:
            return "No seen-but-unapplied postings in the tracker yet."
        lines = "\n".join(f"- {o.get('role') or o['url']} ({o['url']})" for o in seen)
        return f"Opened, not applied:\n{lines}"
    if any(word in msg for word in ("tracker", "applications", "opportunities", "conferences")):
        if not opps:
            return "The tracker is empty. Add a program in Programs, or let mail and browsing capture one."
        states: dict[str, int] = {}
        kinds: dict[str, int] = {}
        for opp in opps:
            states[opp["state"]] = states.get(opp["state"], 0) + 1
            kinds[opp["kind"]] = kinds.get(opp["kind"], 0) + 1
        active = [o for o in opps if o["state"] not in {"offer", "rejected", "skipped", "ignored"}]
        state_line = ", ".join(f"{value} {key}" for key, value in sorted(states.items()))
        kind_line = ", ".join(f"{value} {key}" for key, value in sorted(kinds.items()))
        return f"You have {len(opps)} tracked: {kind_line}. Status: {state_line}. {len(active)} still active."
    if snapshot["needs_gate"]:
        return "No plan for today. The gate is still waiting."
    plan = snapshot["plan"]
    n = len(snapshot["opportunities"])
    return (
        f"Ollama is off, so this is a raw snapshot. Outcomes: {plan['outcomes']}. "
        f"{n} opportunities tracked. {len(snapshot['approvals'])} pending approvals. "
        f"{len(snapshot['mail'])} open mail cards."
    )


def main() -> None:
    import uvicorn

    host = os.environ.get("TIMELESS_HOST", "0.0.0.0")
    port = int(os.environ.get("TIMELESS_PORT", "8787"))
    uvicorn.run("timeless.app:create_app", factory=True, host=host, port=port)
