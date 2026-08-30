from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from typing import Any

from timeless.classify_event import URL_RE, classify_event, is_join_url, looks_like_presentation, looks_like_submission, mail_matches_event, pick_join_url
from timeless.clock import day_key, due_recap_day, utc_now, zone
from timeless.db import connect
from timeless.ingest import canonicalize_program_url, classify_screen_text, program_kind_for_url
from timeless.mailer import first_url, parse_when, program_kind
from timeless.praise import praise_for
from timeless.productivity import classify_activity, productivity_summary
from timeless.quiet import PANIC_MINUTES, QUIET_LEVELS, blocks_halt, end_from_minutes, iso as quiet_iso, parse_iso, quiet_public
from timeless.reminders import reminder_fires

VALID_STATES = frozenset(
    {"seen", "applied", "shortlisted", "interview", "waiting", "offer", "rejected", "skipped", "ignored"}
)
VALID_KINDS = frozenset({"internship", "hackathon", "conference", "other"})
MEETING_ACKS = frozenset({"join", "im_in"})


def _now() -> datetime:
    return utc_now()


def _iso(dt: datetime | None = None) -> str:
    return (dt or _now()).strftime("%Y-%m-%dT%H:%M:%SZ")


def _day(dt: datetime | None = None) -> str:
    return day_key(dt)


def row_to_dict(row) -> dict[str, Any]:
    return dict(row) if row is not None else {}


class Store:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn = connect(db_path)

    def close(self) -> None:
        self.conn.close()

    def heartbeat(self, sensor: str, detail: str | None = None) -> None:
        self.conn.execute(
            """
            INSERT INTO heartbeats(sensor, last_seen, detail) VALUES (?, ?, ?)
            ON CONFLICT(sensor) DO UPDATE SET last_seen=excluded.last_seen, detail=excluded.detail
            """,
            (sensor, _iso(), detail),
        )
        self.conn.commit()

    def heartbeats(self) -> list[dict[str, Any]]:
        return [row_to_dict(r) for r in self.conn.execute("SELECT * FROM heartbeats ORDER BY sensor")]

    def add_event(self, source: str, summary: str, payload: dict | None = None) -> int:
        cur = self.conn.execute(
            "INSERT INTO events(source, ts, summary, payload) VALUES (?, ?, ?, ?)",
            (source, _iso(), summary, json.dumps(payload or {})),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def add_activity(
        self,
        *,
        source: str,
        source_id: str,
        ts: str,
        duration_seconds: float,
        app: str | None = None,
        host: str | None = None,
        title: str | None = None,
    ) -> dict[str, Any]:
        timestamp = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        category, productivity = classify_activity(app, title, host)
        self.conn.execute(
            """INSERT INTO activity_samples(source, source_id, ts, duration_seconds, app, host, title, category, productivity)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(source, source_id) DO UPDATE SET
                 ts=excluded.ts, duration_seconds=excluded.duration_seconds, app=excluded.app,
                 host=excluded.host, title=excluded.title, category=excluded.category,
                 productivity=excluded.productivity""",
            (source[:40], source_id[:240], _iso(timestamp), max(0.0, min(float(duration_seconds), 86400.0)), (app or "")[:120], (host or "")[:200], (title or "")[:240], category, productivity),
        )
        self.conn.commit()
        row = self.conn.execute("SELECT * FROM activity_samples WHERE source=? AND source_id=?", (source[:40], source_id[:240])).fetchone()
        return row_to_dict(row)

    def activities_on_day(self, day: str) -> list[dict[str, Any]]:
        try:
            local_start = datetime.strptime(day, "%Y-%m-%d").replace(tzinfo=zone())
        except ValueError:
            return []
        start = _iso(local_start.astimezone(timezone.utc))
        end = _iso((local_start + timedelta(days=1)).astimezone(timezone.utc))
        return [row_to_dict(row) for row in self.conn.execute("SELECT * FROM activity_samples WHERE ts>=? AND ts<? ORDER BY ts", (start, end))]

    def productivity_on_day(self, day: str) -> dict[str, Any]:
        return productivity_summary(self.activities_on_day(day), self.get_plan(day))

    def latest_event_age_seconds(self) -> float | None:
        row = self.conn.execute("SELECT ts FROM events ORDER BY ts DESC LIMIT 1").fetchone()
        if not row:
            return None
        ts = datetime.strptime(row["ts"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        return (_now() - ts).total_seconds()

    def save_plan(self, outcomes: str, timeline: list[dict], day: str | None = None) -> dict[str, Any]:
        outcomes = (outcomes or "").strip()
        if not outcomes:
            raise ValueError("outcomes required")
        if not timeline:
            raise ValueError("timeline required")
        for block in timeline:
            if not str(block.get("task") or "").strip():
                raise ValueError("each block needs a task")
        day = day or _day()
        now = _iso()
        payload = json.dumps(timeline)
        existing = self.conn.execute("SELECT id FROM daily_plans WHERE day=?", (day,)).fetchone()
        if existing:
            self.conn.execute(
                "UPDATE daily_plans SET outcomes=?, timeline=?, updated_at=? WHERE day=?",
                (outcomes, payload, now, day),
            )
        else:
            self.conn.execute(
                """
                INSERT INTO daily_plans(day, outcomes, timeline, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (day, outcomes, payload, now, now),
            )
        self.conn.commit()
        return self.get_plan(day)

    def get_plan(self, day: str | None = None) -> dict[str, Any] | None:
        day = day or _day()
        row = self.conn.execute("SELECT * FROM daily_plans WHERE day=?", (day,)).fetchone()
        if not row:
            return None
        data = row_to_dict(row)
        data["timeline"] = json.loads(data["timeline"])
        return data

    def add_ritual(
        self,
        name: str,
        launch_url: str | None = None,
        app_bundle: str | None = None,
        weekdays: str = "1,2,3,4,5",
        match_host: str | None = None,
        min_minutes: int | None = None,
    ) -> int:
        cur = self.conn.execute(
            """
            INSERT INTO rituals(name, launch_url, app_bundle, weekdays, match_host, min_minutes)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (name, launch_url, app_bundle, weekdays, match_host, min_minutes),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def list_rituals(self) -> list[dict[str, Any]]:
        return [row_to_dict(r) for r in self.conn.execute("SELECT * FROM rituals ORDER BY id")]

    def complete_ritual(self, ritual_id: int, day: str | None = None) -> dict[str, Any]:
        day = day or _day()
        ritual = self.conn.execute("SELECT * FROM rituals WHERE id=?", (ritual_id,)).fetchone()
        if not ritual:
            raise ValueError("unknown ritual")
        praise = praise_for(ritual["name"])
        try:
            self.conn.execute(
                "INSERT INTO ritual_completions(ritual_id, day, praise, created_at) VALUES (?, ?, ?, ?)",
                (ritual_id, day, praise, _iso()),
            )
        except Exception as exc:
            raise ValueError("already completed today") from exc
        self.conn.commit()
        return {"ritual_id": ritual_id, "day": day, "praise": praise}

    def upsert_opportunity(
        self,
        *,
        url: str,
        company: str | None = None,
        role: str | None = None,
        state: str = "seen",
        kind: str = "internship",
        deadline_at: str | None = None,
        source: str = "url",
    ) -> dict[str, Any]:
        if url.startswith(("http://", "https://")):
            url = canonicalize_program_url(url)
        if state not in VALID_STATES:
            raise ValueError("bad state")
        if kind not in VALID_KINDS:
            raise ValueError("bad kind")
        now = _iso()
        row = self.conn.execute("SELECT * FROM opportunities WHERE url=?", (url,)).fetchone()
        if row:
            self.conn.execute(
                """
                UPDATE opportunities SET company=COALESCE(?, company), role=COALESCE(?, role),
                    deadline_at=COALESCE(?, deadline_at), kind=COALESCE(?, kind), updated_at=?
                WHERE id=?
                """,
                (company, role, deadline_at, kind, now, row["id"]),
            )
            self.conn.commit()
            out = row_to_dict(self.conn.execute("SELECT * FROM opportunities WHERE id=?", (row["id"],)).fetchone())
            self.set_setting("google_tracker_dirty", "1")
            self._sync_opportunity_deadline(out)
            return out
        cur = self.conn.execute(
            """
            INSERT INTO opportunities(company, role, url, state, kind, deadline_at, source, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (company, role, url, state, kind, deadline_at, source, now, now),
        )
        self.conn.commit()
        out = row_to_dict(self.conn.execute("SELECT * FROM opportunities WHERE id=?", (cur.lastrowid,)).fetchone())
        self.set_setting("google_tracker_dirty", "1")
        self._sync_opportunity_deadline(out)
        return out

    def _sync_opportunity_deadline(self, opportunity: dict[str, Any]) -> None:
        uid = f"opportunity:{opportunity['id']}:deadline"
        raw = (opportunity.get("deadline_at") or "").strip()
        if not raw:
            self.conn.execute("DELETE FROM reminders WHERE event_uid=?", (uid,))
            self.conn.execute("DELETE FROM meetings WHERE uid=?", (uid,))
            self.conn.commit()
            return
        try:
            deadline = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return
        if deadline.tzinfo is None:
            if len(raw) == 10:
                deadline = deadline.replace(hour=17, minute=0)
            deadline = deadline.replace(tzinfo=zone())
        deadline = deadline.astimezone(timezone.utc)
        self.upsert_meeting(
            uid=uid,
            title=f"Deadline · {opportunity.get('role') or opportunity.get('company') or 'Program'}",
            start_at=_iso(deadline),
            end_at=_iso(deadline + timedelta(minutes=30)),
            notes=opportunity.get("url"),
            kind="deadline",
            modality="virtual",
            reminder_only=True,
        )

    def set_opportunity_state(self, opportunity_id: int, state: str, kind: str | None = None) -> dict[str, Any]:
        if state not in VALID_STATES:
            raise ValueError("bad state")
        if kind:
            if kind not in VALID_KINDS:
                raise ValueError("bad kind")
            self.conn.execute("UPDATE opportunities SET kind=? WHERE id=?", (kind, opportunity_id))
        self.conn.execute(
            "UPDATE opportunities SET state=?, updated_at=? WHERE id=?",
            (state, _iso(), opportunity_id),
        )
        self.conn.commit()
        row = self.conn.execute("SELECT * FROM opportunities WHERE id=?", (opportunity_id,)).fetchone()
        if not row:
            raise ValueError("unknown opportunity")
        self.set_setting("google_tracker_dirty", "1")
        return row_to_dict(row)

    def patch_opportunity(
        self,
        opportunity_id: int,
        *,
        company: str | None = None,
        role: str | None = None,
        kind: str | None = None,
        url: str | None = None,
        deadline_at: str | None = None,
    ) -> dict[str, Any]:
        row = self.conn.execute("SELECT * FROM opportunities WHERE id=?", (opportunity_id,)).fetchone()
        if not row:
            raise ValueError("unknown opportunity")
        if kind is not None and kind not in VALID_KINDS:
            raise ValueError("bad kind")
        self.conn.execute(
            """
            UPDATE opportunities SET
                company=COALESCE(?, company),
                role=COALESCE(?, role),
                kind=COALESCE(?, kind),
                url=COALESCE(?, url),
                deadline_at=COALESCE(?, deadline_at),
                updated_at=?
            WHERE id=?
            """,
            (company, role, kind, url, deadline_at, _iso(), opportunity_id),
        )
        self.conn.commit()
        out = row_to_dict(self.conn.execute("SELECT * FROM opportunities WHERE id=?", (opportunity_id,)).fetchone())
        self.set_setting("google_tracker_dirty", "1")
        self._sync_opportunity_deadline(out)
        return out

    def list_opportunities(self) -> list[dict[str, Any]]:
        return [row_to_dict(r) for r in self.conn.execute("SELECT * FROM opportunities ORDER BY updated_at DESC")]

    def get_setting(self, key: str) -> str | None:
        row = self.conn.execute("SELECT value FROM app_settings WHERE key=?", (key,)).fetchone()
        return str(row["value"]) if row else None

    def set_setting(self, key: str, value: str) -> None:
        self.conn.execute(
            """INSERT INTO app_settings(key, value, updated_at) VALUES (?, ?, ?)
               ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at""",
            (key, value, _iso()),
        )
        self.conn.commit()

    def delete_setting(self, key: str) -> None:
        self.conn.execute("DELETE FROM app_settings WHERE key=?", (key,))
        self.conn.commit()

    def propose(self, kind: str, payload: dict, ttl_days: int = 7) -> dict[str, Any]:
        now = _now()
        cur = self.conn.execute(
            """
            INSERT INTO pending_approvals(kind, payload, status, created_at, expires_at)
            VALUES (?, ?, 'pending', ?, ?)
            """,
            (kind, json.dumps(payload), _iso(now), _iso(now + timedelta(days=ttl_days))),
        )
        self.conn.commit()
        return self.get_approval(int(cur.lastrowid))

    def get_approval(self, approval_id: int) -> dict[str, Any]:
        row = self.conn.execute("SELECT * FROM pending_approvals WHERE id=?", (approval_id,)).fetchone()
        if not row:
            raise ValueError("unknown approval")
        data = row_to_dict(row)
        data["payload"] = json.loads(data["payload"])
        return data

    def list_approvals(self, status: str = "pending") -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT * FROM pending_approvals WHERE status=? ORDER BY id",
            (status,),
        )
        out = []
        for row in rows:
            data = row_to_dict(row)
            try:
                data["payload"] = json.loads(data["payload"])
            except (TypeError, json.JSONDecodeError):
                data["payload"] = {"parse_error": True, "raw": data.get("payload")}
            out.append(data)
        return out

    def expire_approvals(self, now: datetime | None = None) -> int:
        now = now or _now()
        cur = self.conn.execute(
            """
            UPDATE pending_approvals SET status='expired'
            WHERE status='pending' AND expires_at <= ?
            """,
            (_iso(now),),
        )
        self.conn.commit()
        return cur.rowcount

    def decide_approval(self, approval_id: int, accept: bool, extra: dict | None = None) -> dict[str, Any]:
        self.expire_approvals()
        row = self.conn.execute("SELECT * FROM pending_approvals WHERE id=?", (approval_id,)).fetchone()
        if not row:
            raise ValueError("unknown approval")
        if row["status"] != "pending":
            raise ValueError("approval not pending")
        payload = json.loads(row["payload"])
        if extra:
            payload.update(extra)
        if accept:
            self._apply_approval(row["kind"], payload)
            status = "accepted"
        else:
            status = "rejected"
        self.conn.execute(
            "UPDATE pending_approvals SET status=?, payload=? WHERE id=?",
            (status, json.dumps(payload), approval_id),
        )
        self.conn.commit()
        return self.get_approval(approval_id)

    def _apply_approval(self, kind: str, payload: dict) -> None:
        if kind in {"mark_applied", "opportunity_applied"}:
            oid = payload.get("opportunity_id")
            if not oid and payload.get("url"):
                opp = self.upsert_opportunity(url=payload["url"], company=payload.get("company"), role=payload.get("role"))
                oid = opp["id"]
            if not oid:
                raise ValueError("approval missing posting — add a URL or pick a tracked opportunity first")
            self.set_opportunity_state(int(oid), "applied")
        elif kind in {"mark_skipped", "opportunity_skip"}:
            oid = payload.get("opportunity_id")
            if not oid:
                raise ValueError("approval missing opportunity")
            self.set_opportunity_state(int(oid), "skipped")
        elif kind == "keep_seen":
            oid = payload.get("opportunity_id")
            if not oid:
                raise ValueError("approval missing opportunity")
            self.set_opportunity_state(int(oid), "seen")
        elif kind == "pin_ritual":
            name = payload.get("name")
            if not name:
                raise ValueError("approval missing ritual name")
            self.add_ritual(
                name=name,
                launch_url=payload.get("launch_url"),
                match_host=payload.get("match_host"),
            )
        elif kind == "do_send":
            # Accepting still does not send or submit; the hands layer is not built.
            return

    def ingest_url(self, url: str, title: str | None = None, source: str = "url") -> dict[str, Any]:
        src = "phone" if source == "phone" else "url"
        kind = program_kind_for_url(url, title)
        if src == "phone":
            self.heartbeat("phone_aw", "browser activity received")
        else:
            self.heartbeat("mac_browser", "browser activity received")
        if not kind:
            return {"job": False, "tracked": False, "url": url}
        clean_url = canonicalize_program_url(url)
        self.add_event(src, title or clean_url, {"url": clean_url, "title": title, "kind": kind})
        opp = self.upsert_opportunity(url=clean_url, role=title, company=None, kind=kind, source="url")
        return {"job": kind == "internship", "tracked": True, "kind": kind, "opportunity": opp}

    def ingest_screen_text(self, text: str, url: str | None = None) -> dict[str, Any]:
        kind = classify_screen_text(text)
        self.add_event("screen", (text or "")[:200], {"url": url, "kind": kind})
        if not kind:
            return {"kind": None}
        if url:
            opp = self.upsert_opportunity(url=url, source="screen")
        else:
            opp = None
        if kind == "confirmation":
            if self.is_dormant():
                return {"kind": kind, "skipped": "dormant"}
            approval = self.propose(
                "mark_applied",
                {"opportunity_id": opp["id"] if opp else None, "url": url, "snippet": text[:280]},
            )
            return {"kind": kind, "approval": approval}
        if kind == "requirement_miss":
            if self.is_dormant():
                return {"kind": kind, "skipped": "dormant"}
            approval = self.propose(
                "opportunity_skip",
                {
                    "opportunity_id": opp["id"] if opp else None,
                    "url": url,
                    "snippet": text[:280],
                    "prompt": "skip (don't remind), keep as seen (reapply later), or reject to ignore",
                },
            )
            return {"kind": kind, "approval": approval}
        return {"kind": kind}

    def ingest_phone(self, summary: str, payload: dict | None = None) -> int:
        self.heartbeat("phone_a11y", summary)
        return self.add_event("phone", summary, payload)

    def add_mail_action(self, message_id: str, account: str, subject: str, classification: str, card: str) -> dict[str, Any]:
        existing = self.conn.execute("SELECT * FROM mail_actions WHERE message_id=?", (message_id,)).fetchone()
        if not existing:
            cur = self.conn.execute(
                """
                INSERT INTO mail_actions(message_id, account, subject, classification, card, status)
                VALUES (?, ?, ?, ?, ?, 'open')
                """,
                (message_id, account, subject, classification, card),
            )
            self.conn.commit()
            row = row_to_dict(self.conn.execute("SELECT * FROM mail_actions WHERE id=?", (cur.lastrowid,)).fetchone())
        else:
            row = row_to_dict(existing)
        self._promote_mail(message_id, subject, classification, card)
        return row

    def _promote_mail(self, message_id: str, subject: str, classification: str, card: str) -> None:
        blob = f"{subject} {card}"
        url = first_url(blob) or f"mail:{message_id}"
        kind = program_kind(classification)
        if not kind and url.startswith(("http://", "https://")):
            kind = program_kind_for_url(url, blob)
        if not kind:
            guessed_kind, _ = classify_event(blob, None, None)
            kind = guessed_kind if guessed_kind in {"hackathon", "conference"} else None
        if kind and is_join_url(url):
            url = f"mail:{message_id}"
        when = parse_when(blob)
        deadline_at = _iso(when) if when and looks_like_submission(blob) else None
        if kind:
            state = "seen"
            if classification == "interview":
                state = "interview"
            elif classification == "rejection":
                state = "rejected"
            existing = self.conn.execute("SELECT * FROM opportunities WHERE url=?", (url,)).fetchone()
            if existing:
                if classification in {"interview", "rejection"}:
                    self.set_opportunity_state(existing["id"], state, kind)
                else:
                    self.upsert_opportunity(url=url, role=subject, kind=kind, deadline_at=deadline_at, source="mail")
            else:
                self.upsert_opportunity(url=url, role=subject, kind=kind, state=state, deadline_at=deadline_at, source="mail")
        if when and (kind in {"hackathon", "conference"} or classification in {"hackathon", "conference", "interview"}):
            join = pick_join_url(blob)
            end = when + timedelta(hours=2)
            self.upsert_meeting(
                uid=f"mail:{message_id}",
                title=subject,
                start_at=_iso(when),
                end_at=_iso(end),
                join_url=join,
                notes=card,
                kind="interview" if classification == "interview" else (kind or "conference"),
                modality="virtual" if join else None,
            )

    def list_mail_actions(self, status: str = "open") -> list[dict[str, Any]]:
        return [
            row_to_dict(r)
            for r in self.conn.execute("SELECT * FROM mail_actions WHERE status=? ORDER BY id DESC", (status,))
        ]

    def _resolve_join(self, title: str, join_url: str | None, location: str | None, notes: str | None) -> str | None:
        picked = pick_join_url(notes, location, preferred=join_url)
        if picked:
            return picked
        for mail in self.list_mail_actions("open"):
            if mail_matches_event(title, mail.get("subject") or ""):
                found = pick_join_url(mail.get("card"), mail.get("subject"))
                if found:
                    return found
        return None

    def upsert_meeting(
        self,
        uid: str,
        title: str,
        start_at: str,
        end_at: str,
        join_url: str | None = None,
        location: str | None = None,
        notes: str | None = None,
        kind: str | None = None,
        modality: str | None = None,
        reminder_only: bool = False,
    ) -> dict[str, Any]:
        existing = self.conn.execute("SELECT * FROM meetings WHERE uid=?", (uid,)).fetchone()
        locked = bool(existing["join_locked"]) if existing else False
        picked = self._resolve_join(title, join_url, location, notes)
        if locked:
            stored_join = existing["join_url"]
            lock_val = existing["join_locked"]
        else:
            stored_join = picked
            lock_val = existing["join_locked"] if existing else 0
        self.conn.execute(
            """
            INSERT INTO meetings(uid, title, start_at, end_at, join_url, join_locked, location, notes, reminder_only, ack, acked_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL)
            ON CONFLICT(uid) DO UPDATE SET
                title=excluded.title, start_at=excluded.start_at, end_at=excluded.end_at,
                join_url=excluded.join_url, join_locked=excluded.join_locked,
                location=excluded.location, notes=excluded.notes, reminder_only=excluded.reminder_only
            """,
            (uid, title, start_at, end_at, stored_join, lock_val, location, notes, int(reminder_only)),
        )
        self.conn.commit()
        row = row_to_dict(self.conn.execute("SELECT * FROM meetings WHERE uid=?", (uid,)).fetchone())
        if not row.get("confirmed"):
            guess_kind, guess_mod = classify_event(title, stored_join, location, notes)
            kind = kind or guess_kind
            modality = modality or guess_mod
            reminder_only = reminder_only or kind in {"deadline", "calendar_note"}
            self.conn.execute("UPDATE meetings SET kind=?, modality=?, reminder_only=? WHERE uid=?", (kind, modality, int(reminder_only), uid))
            self.conn.commit()
        self.sync_reminders(uid)
        out = row_to_dict(self.conn.execute("SELECT * FROM meetings WHERE uid=?", (uid,)).fetchone())
        if not reminder_only and out.get("kind") in {"hackathon", "conference"}:
            program_url = None
            for match in URL_RE.finditer(" ".join(x for x in (notes, location) if x)):
                candidate = match.group(0).rstrip(").,")
                if not is_join_url(candidate):
                    program_url = candidate
                    break
            self.upsert_opportunity(
                url=program_url or (uid if uid.startswith("mail:") else f"calendar:{uid}"),
                role=title,
                kind=out["kind"],
                source="calendar" if not uid.startswith("mail:") else "mail",
            )
        return out

    def patch_meeting(
        self,
        meeting_id: int,
        *,
        join_url: str | None = None,
        modality: str | None = None,
        kind: str | None = None,
        title: str | None = None,
    ) -> dict[str, Any]:
        row = self.conn.execute("SELECT * FROM meetings WHERE id=?", (meeting_id,)).fetchone()
        if not row:
            raise ValueError("unknown meeting")
        if title is not None:
            self.conn.execute("UPDATE meetings SET title=? WHERE id=?", (title, meeting_id))
        if kind is not None:
            self.conn.execute("UPDATE meetings SET kind=? WHERE id=?", (kind, meeting_id))
        if modality is not None:
            self.conn.execute("UPDATE meetings SET modality=? WHERE id=?", (modality, meeting_id))
        if join_url is not None:
            self.conn.execute(
                "UPDATE meetings SET join_url=?, join_locked=1 WHERE id=?",
                (join_url, meeting_id),
            )
        self.conn.commit()
        uid = row["uid"]
        self.sync_reminders(uid)
        return row_to_dict(self.conn.execute("SELECT * FROM meetings WHERE id=?", (meeting_id,)).fetchone())

    def sync_reminders(self, uid: str) -> None:
        row = self.conn.execute("SELECT * FROM meetings WHERE uid=?", (uid,)).fetchone()
        if not row:
            return
        start = datetime.fromisoformat(row["start_at"].replace("Z", "+00:00"))
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        kind = row["kind"] or "meeting"
        modality = row["modality"] or "virtual"
        title = row["title"] or ""
        notes = row["notes"] or ""
        submit = start if looks_like_submission(title, notes) else None
        present = start if looks_like_presentation(title, notes) else None
        if submit and kind == "hackathon" and looks_like_submission(title, notes):
            fires = [("submit_4h", start - timedelta(hours=4))]
        elif present and looks_like_presentation(title, notes) and not looks_like_submission(title, notes):
            fires = [("present_30m", start - timedelta(minutes=30))]
        else:
            fires = reminder_fires(kind, modality, start, submit=submit, present=present)
        purposes = [purpose for purpose, _ in fires]
        if purposes:
            placeholders = ",".join("?" for _ in purposes)
            self.conn.execute(
                f"DELETE FROM reminders WHERE event_uid=? AND acked_at IS NULL AND purpose NOT IN ({placeholders})",
                (uid, *purposes),
            )
        else:
            self.conn.execute("DELETE FROM reminders WHERE event_uid=? AND acked_at IS NULL", (uid,))
        for purpose, due in fires:
            self.conn.execute(
                """
                INSERT INTO reminders(event_uid, purpose, due_at, acked_at)
                VALUES (?, ?, ?, NULL)
                ON CONFLICT(event_uid, purpose) DO UPDATE SET due_at=excluded.due_at
                WHERE reminders.acked_at IS NULL
                """,
                (uid, purpose, _iso(due.astimezone(timezone.utc))),
            )
        self._maybe_auto_interview_quiet(row_to_dict(row))
        self.conn.commit()

    def _maybe_auto_interview_quiet(self, meeting: dict[str, Any]) -> None:
        kind = (meeting.get("kind") or "").lower()
        title = meeting.get("title") or ""
        if kind != "interview" and not re.search(r"\binterview\b", title, re.I):
            return
        start = parse_iso(meeting["start_at"])
        end = parse_iso(meeting["end_at"])
        now = _now()
        if start.astimezone(timezone.utc) < now - timedelta(hours=1):
            return
        self.ensure_auto_quiet(
            meeting_id=int(meeting["id"]),
            level="quiet",
            starts_at=quiet_iso(start - timedelta(minutes=5)),
            ends_at=quiet_iso(end + timedelta(minutes=5)),
            reason=f"Interview: {title[:80]}",
            source="auto_interview",
        )

    def ensure_auto_quiet(
        self,
        *,
        meeting_id: int,
        level: str,
        starts_at: str,
        ends_at: str,
        reason: str,
        source: str,
    ) -> dict[str, Any] | None:
        existing = self.conn.execute(
            "SELECT * FROM quiet_periods WHERE meeting_id=? AND source=? LIMIT 1",
            (meeting_id, source),
        ).fetchone()
        if existing:
            return row_to_dict(existing)
        return self.create_quiet(
            level=level,
            starts_at=starts_at,
            ends_at=ends_at,
            reason=reason,
            source=source,
            meeting_id=meeting_id,
        )

    def create_quiet(
        self,
        *,
        level: str,
        starts_at: str | None = None,
        ends_at: str | None = None,
        minutes: int | None = None,
        reason: str | None = None,
        source: str = "manual",
        meeting_id: int | None = None,
    ) -> dict[str, Any]:
        if level not in QUIET_LEVELS:
            raise ValueError("level must be mild, quiet, or dormant")
        now = _now()
        start_s = starts_at or _iso(now)
        if ends_at:
            end_s = ends_at
        elif minutes is not None:
            end_s = end_from_minutes(minutes, now)
        else:
            end_s = end_from_minutes(60, now)
        if parse_iso(end_s) <= parse_iso(start_s):
            raise ValueError("ends_at must be after starts_at")
        cur = self.conn.execute(
            """
            INSERT INTO quiet_periods(level, starts_at, ends_at, reason, source, meeting_id)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (level, start_s, end_s, reason, source, meeting_id),
        )
        self.conn.commit()
        return row_to_dict(self.conn.execute("SELECT * FROM quiet_periods WHERE id=?", (cur.lastrowid,)).fetchone())

    def end_quiet(self, quiet_id: int) -> dict[str, Any]:
        row = self.conn.execute("SELECT * FROM quiet_periods WHERE id=?", (quiet_id,)).fetchone()
        if not row:
            raise ValueError("unknown quiet period")
        now_s = _iso()
        self.conn.execute("UPDATE quiet_periods SET ends_at=? WHERE id=?", (now_s, quiet_id))
        self.conn.commit()
        return row_to_dict(self.conn.execute("SELECT * FROM quiet_periods WHERE id=?", (quiet_id,)).fetchone())

    def panic_quiet(self) -> dict[str, Any]:
        return self.create_quiet(level="dormant", minutes=PANIC_MINUTES, reason="panic", source="manual")

    def list_quiet(self, now: datetime | None = None) -> list[dict[str, Any]]:
        now_s = _iso(now or _now())
        rows = self.conn.execute(
            """
            SELECT * FROM quiet_periods
            WHERE ends_at > ?
            ORDER BY starts_at
            """,
            (now_s,),
        )
        return [row_to_dict(r) for r in rows]

    def active_quiet(self, now: datetime | None = None) -> dict[str, Any] | None:
        now_dt = now or _now()
        now_s = _iso(now_dt)
        row = self.conn.execute(
            """
            SELECT * FROM quiet_periods
            WHERE starts_at <= ? AND ends_at > ?
            ORDER BY CASE level WHEN 'dormant' THEN 0 WHEN 'quiet' THEN 1 ELSE 2 END
            LIMIT 1
            """,
            (now_s, now_s),
        ).fetchone()
        return quiet_public(row_to_dict(row), now_dt) if row else None

    def is_dormant(self, now: datetime | None = None) -> bool:
        q = self.active_quiet(now)
        return bool(q and q.get("level") == "dormant")

    def quiet_summary(self, now: datetime | None = None) -> dict[str, Any] | None:
        return self.active_quiet(now)

    def _meeting_join_url(self, data: dict[str, Any]) -> str | None:
        return pick_join_url(data.get("join_url"), data.get("notes"), data.get("location"))

    def _sanitize_halt(self, data: dict[str, Any]) -> dict[str, Any]:
        if not data:
            return data
        cleaned = pick_join_url(data.get("join_url"), data.get("notes"), data.get("location"))
        if cleaned:
            data["join_url"] = cleaned
        return data

    def _meeting_for_halt(self, data: dict[str, Any]) -> dict[str, Any]:
        if data.get("halt_kind") == "reminder":
            mid = data.get("meeting_id")
            if mid:
                row = self.conn.execute("SELECT * FROM meetings WHERE id=?", (mid,)).fetchone()
                if row:
                    return row_to_dict(row)
        if data.get("id") and not data.get("halt_kind"):
            row = self.conn.execute("SELECT * FROM meetings WHERE id=?", (data["id"],)).fetchone()
            if row:
                return row_to_dict(row)
        return data

    def _enrich_halt(self, data: dict[str, Any] | None) -> dict[str, Any] | None:
        if not data:
            return data
        out = self._sanitize_halt(dict(data))
        meeting = self._meeting_for_halt(out)
        join_url = self._meeting_join_url(meeting) or out.get("join_url")
        modality = (meeting.get("modality") or out.get("modality") or "virtual").lower()
        physical = modality == "physical"
        reminder = out.get("halt_kind") == "reminder"
        out["requires_join"] = bool(join_url) and not physical
        out["can_im_in"] = not reminder and not out["requires_join"]
        out["can_headed"] = reminder and physical and out.get("purpose") == "start_2h"
        if out["requires_join"]:
            out["im_in_hint"] = "Join opens the meeting link. I'm in is disabled for virtual calls."
        elif physical:
            out["im_in_hint"] = "Tap twice to confirm you are on site."
        else:
            out["im_in_hint"] = "Tap twice to confirm you are on the call."
        return out

    def join_meeting(self, meeting_id: int, reminder_id: int | None = None) -> dict[str, Any]:
        row = self.conn.execute("SELECT * FROM meetings WHERE id=?", (meeting_id,)).fetchone()
        if not row:
            raise ValueError("unknown meeting")
        data = row_to_dict(row)
        url = self._meeting_join_url(data)
        if not url:
            raise ValueError("no join link for this meeting")
        from timeless.hands import run as run_hands

        run_hands({"action": "open_url", "target": "mac", "url": url})
        try:
            run_hands({"action": "open_url", "target": "phone", "url": url})
        except Exception:
            pass
        out = self.ack_meeting(meeting_id, "join")
        if reminder_id is not None:
            self.conn.execute(
                "UPDATE reminders SET acked_at=? WHERE id=? AND acked_at IS NULL",
                (_iso(), reminder_id),
            )
            self.conn.commit()
        return {"ok": True, "url": url, "meeting": out}

    def due_reminder(self, now: datetime | None = None) -> dict[str, Any] | None:
        now_dt = now or _now()
        now_s = _iso(now_dt)
        floor = _iso(now_dt - timedelta(hours=18))
        row = self.conn.execute(
            """
            SELECT r.id, r.purpose, r.due_at, r.event_uid, m.id AS meeting_id, m.title, m.join_url,
                   m.kind, m.modality, m.confirmed, m.start_at, m.end_at, m.location
            FROM reminders r
            JOIN meetings m ON m.uid = r.event_uid
            WHERE r.acked_at IS NULL AND r.due_at <= ? AND r.due_at >= ? AND m.end_at > ?
              AND NOT (r.purpose LIKE 'start_%' AND m.start_at <= ?)
            ORDER BY r.due_at LIMIT 1
            """,
            (now_s, floor, now_s, now_s),
        ).fetchone()
        if not row:
            return None
        data = row_to_dict(row)
        data["halt_kind"] = "reminder"
        return self._enrich_halt(data)

    def ack_reminder(self, reminder_id: int, action: str, kind: str | None = None, modality: str | None = None) -> dict[str, Any]:
        row = self.conn.execute("SELECT * FROM reminders WHERE id=?", (reminder_id,)).fetchone()
        if not row:
            raise ValueError("unknown reminder")
        if action not in {"confirm", "change", "headed", "dismiss", "im_in"}:
            raise ValueError("unsupported reminder action")
        if action == "headed":
            meeting = self.conn.execute("SELECT modality FROM meetings WHERE uid=?", (row["event_uid"],)).fetchone()
            if row["purpose"] != "start_2h" or not meeting or meeting["modality"] != "physical":
                raise ValueError("headed is only available for the two-hour physical reminder")
        if action in {"confirm", "change"}:
            self.conn.execute(
                "UPDATE meetings SET kind=COALESCE(?, kind), modality=COALESCE(?, modality), confirmed=1 WHERE uid=?",
                (kind, modality, row["event_uid"]),
            )
            self.conn.execute("UPDATE reminders SET acked_at=? WHERE id=? AND acked_at IS NULL", (_iso(), reminder_id))
            self.sync_reminders(row["event_uid"])
            self.conn.commit()
            return self.due_reminder() or row_to_dict(row)
        self.conn.execute("UPDATE reminders SET acked_at=? WHERE id=?", (_iso(), reminder_id))
        self.conn.commit()
        return row_to_dict(self.conn.execute("SELECT * FROM reminders WHERE id=?", (reminder_id,)).fetchone())

    def ack_meeting(self, meeting_id: int, action: str, *, confirm: bool = False) -> dict[str, Any]:
        if action not in MEETING_ACKS:
            raise ValueError("action must be join or im_in")
        row = self.conn.execute("SELECT * FROM meetings WHERE id=?", (meeting_id,)).fetchone()
        if not row:
            raise ValueError("unknown meeting")
        data = row_to_dict(row)
        if action == "im_in":
            start = parse_iso(data["start_at"])
            if _now() < start.astimezone(timezone.utc) - timedelta(minutes=15):
                raise ValueError("check-in opens 15 minutes before the event")
            join_url = self._meeting_join_url(data)
            virtual = (data.get("modality") or "virtual").lower() != "physical"
            if join_url and virtual:
                raise ValueError("use Join for virtual meetings with a link")
            if not confirm:
                raise ValueError("confirm check-in required")
        self.conn.execute(
            "UPDATE meetings SET ack=?, acked_at=? WHERE id=?",
            (action, _iso(), meeting_id),
        )
        self.conn.commit()
        return row_to_dict(self.conn.execute("SELECT * FROM meetings WHERE id=?", (meeting_id,)).fetchone())

    def close_elapsed_meetings(self, now: datetime | None = None) -> int:
        now_s = _iso(now or _now())
        cur = self.conn.execute(
            """
            UPDATE meetings SET ack='missed'
            WHERE ack IS NULL AND end_at <= ?
            """,
            (now_s,),
        )
        self.conn.commit()
        return cur.rowcount

    def _raw_active_halt(self, now: datetime | None = None) -> dict[str, Any] | None:
        due = self.due_reminder(now)
        if due:
            return due
        now_s = _iso(now or _now())
        row = self.conn.execute(
            """
            SELECT * FROM meetings
            WHERE ack IS NULL AND reminder_only=0 AND start_at <= ? AND end_at > ?
            ORDER BY start_at LIMIT 1
            """,
            (now_s, now_s),
        ).fetchone()
        if not row:
            return None
        return self._enrich_halt(row_to_dict(row))

    def active_halt(self, now: datetime | None = None) -> dict[str, Any] | None:
        self.close_elapsed_meetings(now)
        raw = self._raw_active_halt(now)
        if not raw:
            return None
        quiet = self.active_quiet(now)
        if quiet and blocks_halt(quiet["level"]):
            title = raw.get("title") or "halt"
            self.heartbeat("quiet_mute", f"{quiet['level']}:{title}")
            return None
        if quiet and quiet["level"] == "mild":
            out = dict(raw)
            out["presentation"] = "banner"
            return out
        return raw

    def list_meetings(self) -> list[dict[str, Any]]:
        return [row_to_dict(r) for r in self.conn.execute("SELECT * FROM meetings WHERE reminder_only=0 ORDER BY start_at")]

    def needs_gate(self, day: str | None = None) -> bool:
        return self.get_plan(day) is None

    def get_recap(self, day: str) -> dict[str, Any] | None:
        row = self.conn.execute("SELECT * FROM daily_recaps WHERE day=?", (day,)).fetchone()
        if not row:
            return None
        data = row_to_dict(row)
        data["cards"] = json.loads(data["cards"])
        data["phone_synced"] = bool(data["phone_synced"])
        return data

    def save_recap(self, day: str, cards: list[dict], phone_synced: bool) -> dict[str, Any]:
        payload = json.dumps(cards)
        now = _iso()
        self.conn.execute(
            """
            INSERT INTO daily_recaps(day, cards, phone_synced, generated_at, acked_at)
            VALUES (?, ?, ?, ?, NULL)
            ON CONFLICT(day) DO UPDATE SET
              cards=excluded.cards,
              phone_synced=excluded.phone_synced,
              generated_at=excluded.generated_at
            WHERE daily_recaps.acked_at IS NULL
            """,
            (day, payload, 1 if phone_synced else 0, now),
        )
        self.conn.commit()
        row = self.get_recap(day)
        if row is None:
            raise ValueError("recap missing")
        return row

    def ack_recap(self, day: str | None = None, now: datetime | None = None) -> dict[str, Any]:
        day = day or due_recap_day(now)
        row = self.get_recap(day)
        if not row:
            raise ValueError("unknown recap")
        if row.get("acked_at"):
            return row
        self.conn.execute("UPDATE daily_recaps SET acked_at=? WHERE day=?", (_iso(now), day))
        self.conn.commit()
        recap = self.get_recap(day)
        if recap is None:
            raise ValueError("unknown recap")
        return recap

    def needs_recap(self, now: datetime | None = None) -> bool:
        day = due_recap_day(now)
        row = self.get_recap(day)
        return row is None or not row.get("acked_at")

    def events_on_day(self, day: str) -> list[dict[str, Any]]:
        out = []
        for r in self.conn.execute("SELECT * FROM events ORDER BY ts"):
            data = row_to_dict(r)
            ts = datetime.strptime(data["ts"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            if day_key(ts) != day:
                continue
            if data.get("payload"):
                data["payload"] = json.loads(data["payload"])
            out.append(data)
        return out

    def heatmap(self, weeks: int = 53) -> list[dict[str, Any]]:
        counts: dict[str, int] = {}
        for r in self.conn.execute("SELECT ts FROM events"):
            try:
                ts = datetime.strptime(r["ts"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            except (TypeError, ValueError):
                continue
            key = day_key(ts)
            counts[key] = counts.get(key, 0) + 1
        loc = datetime.strptime(day_key(), "%Y-%m-%d")
        start = loc - timedelta(days=weeks * 7 - 1)
        days = []
        cur = start
        while cur <= loc:
            key = cur.strftime("%Y-%m-%d")
            days.append({"day": key, "count": counts.get(key, 0)})
            cur += timedelta(days=1)
        return days
