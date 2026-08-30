from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import threading
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import httpx


AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
REVOKE_URL = "https://oauth2.googleapis.com/revoke"
SHEETS_URL = "https://sheets.googleapis.com/v4/spreadsheets"
SCOPE = "https://www.googleapis.com/auth/spreadsheets"
DEFAULT_TOKEN_FILE = Path.home() / "Library" / "Application Support" / "Timeless" / "google-oauth.json"
DEFAULT_CLIENT_FILE = Path.home() / "Library" / "Application Support" / "Timeless" / "google-client.json"
HEADERS = ["timeless_id", "company", "role", "kind", "state", "deadline", "url", "source", "updated"]


class GoogleSheetsError(RuntimeError):
    pass


class GoogleSheets:
    """Small, dependency-free OAuth and one-way Sheets publisher.

    Timeless remains authoritative. Publishing replaces only the dedicated
    Timeless Tracker worksheet, avoiding ambiguous bidirectional merges.
    """

    def __init__(self, store, client: httpx.Client | None = None):
        self.store = store
        self.client = client or httpx.Client(timeout=20.0)
        self._states: dict[str, tuple[str, float]] = {}
        self._state_lock = threading.Lock()
        self._sync_lock = threading.Lock()

    @property
    def client_id(self) -> str:
        return os.environ.get("GOOGLE_CLIENT_ID", "").strip() or str(self._client_config().get("client_id", "")).strip()

    @property
    def client_secret(self) -> str:
        return os.environ.get("GOOGLE_CLIENT_SECRET", "").strip() or str(self._client_config().get("client_secret", "")).strip()

    @property
    def redirect_uri(self) -> str:
        return os.environ.get("GOOGLE_REDIRECT_URI", "").strip() or str(self._client_config().get("redirect_uri", "")).strip() or "http://127.0.0.1:8787/oauth/google/callback"

    def _client_config(self) -> dict[str, Any]:
        configured = os.environ.get("TIMELESS_GOOGLE_CLIENT_FILE", "").strip()
        path = Path(configured).expanduser() if configured else DEFAULT_CLIENT_FILE
        try:
            return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        except (OSError, ValueError):
            return {}

    @property
    def token_file(self) -> Path:
        configured = os.environ.get("TIMELESS_GOOGLE_TOKEN_FILE", "").strip()
        return Path(configured).expanduser() if configured else DEFAULT_TOKEN_FILE

    def configured(self) -> bool:
        return bool(self.client_id and self.client_secret)

    def _read_tokens(self) -> dict[str, Any]:
        if not self.token_file.exists():
            return {}
        try:
            return json.loads(self.token_file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def _write_tokens(self, tokens: dict[str, Any]) -> None:
        path = self.token_file
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(".tmp")
        temp.write_text(json.dumps(tokens), encoding="utf-8")
        temp.chmod(0o600)
        temp.replace(path)
        path.chmod(0o600)

    def status(self) -> dict[str, Any]:
        tokens = self._read_tokens()
        spreadsheet_id = self.store.get_setting("google_spreadsheet_id")
        return {
            "configured": self.configured(),
            "connected": bool(tokens.get("refresh_token") or tokens.get("access_token")),
            "spreadsheet_id": spreadsheet_id,
            "spreadsheet_url": f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit" if spreadsheet_id else None,
            "last_synced_at": self.store.get_setting("google_last_synced_at"),
            "dirty": self.store.get_setting("google_tracker_dirty") == "1",
            "mode": "publish",
        }

    def authorization_url(self) -> str:
        if not self.configured():
            raise GoogleSheetsError("Google credentials are not configured")
        state = secrets.token_urlsafe(32)
        verifier = secrets.token_urlsafe(64)
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
        with self._state_lock:
            cutoff = time.time() - 600
            self._states = {k: v for k, v in self._states.items() if v[1] >= cutoff}
            self._states[state] = (verifier, time.time())
        query = urlencode({
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": SCOPE,
            "access_type": "offline",
            "include_granted_scopes": "true",
            "prompt": "consent",
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        })
        return f"{AUTH_URL}?{query}"

    def complete_authorization(self, code: str, state: str) -> None:
        with self._state_lock:
            saved = self._states.pop(state, None)
        if not saved or time.time() - saved[1] > 600:
            raise GoogleSheetsError("OAuth session expired; start the connection again")
        response = self.client.post(TOKEN_URL, data={
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code": code,
            "code_verifier": saved[0],
            "grant_type": "authorization_code",
            "redirect_uri": self.redirect_uri,
        })
        self._raise(response, "Google authorization failed")
        data = response.json()
        if "access_token" not in data:
            raise GoogleSheetsError("Google did not return an access token")
        data["expires_at"] = int(time.time()) + int(data.get("expires_in", 3600)) - 60
        self._write_tokens(data)

    def _access_token(self) -> str:
        tokens = self._read_tokens()
        if tokens.get("access_token") and int(tokens.get("expires_at", 0)) > time.time():
            return str(tokens["access_token"])
        refresh = tokens.get("refresh_token")
        if not refresh:
            raise GoogleSheetsError("Connect Google Sheets first")
        response = self.client.post(TOKEN_URL, data={
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": refresh,
            "grant_type": "refresh_token",
        })
        self._raise(response, "Google session expired; reconnect Sheets")
        fresh = response.json()
        tokens.update(fresh)
        tokens["refresh_token"] = refresh
        tokens["expires_at"] = int(time.time()) + int(fresh.get("expires_in", 3600)) - 60
        self._write_tokens(tokens)
        return str(tokens["access_token"])

    @staticmethod
    def _raise(response: httpx.Response, message: str) -> None:
        if response.is_success:
            return
        try:
            detail = response.json().get("error_description") or response.json().get("error", {}).get("message")
        except (ValueError, AttributeError):
            detail = None
        raise GoogleSheetsError(f"{message}{': ' + detail if detail else ''}")

    def publish(self, opportunities: list[dict[str, Any]]) -> dict[str, Any]:
        if not self._sync_lock.acquire(blocking=False):
            raise GoogleSheetsError("A Google Sheets sync is already running")
        try:
            token = self._access_token()
            auth = {"Authorization": f"Bearer {token}"}
            spreadsheet_id = self.store.get_setting("google_spreadsheet_id")
            if not spreadsheet_id:
                response = self.client.post(SHEETS_URL, headers=auth, json={"properties": {"title": "Timeless Programs Tracker"}, "sheets": [{"properties": {"title": "Tracker"}}]})
                self._raise(response, "Could not create the tracker")
                spreadsheet_id = response.json()["spreadsheetId"]
                self.store.set_setting("google_spreadsheet_id", spreadsheet_id)
            rows = [HEADERS] + [[o.get("id"), o.get("company"), o.get("role"), o.get("kind"), o.get("state"), o.get("deadline_at"), o.get("url"), o.get("source"), o.get("updated_at")] for o in opportunities]
            clear = self.client.post(f"{SHEETS_URL}/{spreadsheet_id}/values/Tracker!A:I:clear", headers=auth, json={})
            self._raise(clear, "Could not clear the tracker sheet")
            update = self.client.put(f"{SHEETS_URL}/{spreadsheet_id}/values/Tracker!A1", headers=auth, params={"valueInputOption": "RAW"}, json={"range": "Tracker!A1", "majorDimension": "ROWS", "values": rows})
            self._raise(update, "Could not update the tracker sheet")
            synced_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            self.store.set_setting("google_last_synced_at", synced_at)
            self.store.set_setting("google_tracker_dirty", "0")
            return {**self.status(), "rows": len(opportunities)}
        finally:
            self._sync_lock.release()

    def disconnect(self) -> None:
        tokens = self._read_tokens()
        token = tokens.get("refresh_token") or tokens.get("access_token")
        if token:
            try:
                self.client.post(REVOKE_URL, params={"token": token})
            except httpx.HTTPError:
                pass
        try:
            self.token_file.unlink(missing_ok=True)
        except OSError as exc:
            raise GoogleSheetsError("Could not remove the local Google token") from exc
