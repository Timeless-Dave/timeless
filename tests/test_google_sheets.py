import json
from urllib.parse import parse_qs, urlparse

import httpx
import pytest

from timeless.google_sheets import GoogleSheets, GoogleSheetsError
from timeless.store import Store


@pytest.fixture
def integration(monkeypatch, tmp_path):
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "client-id")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "client-secret")
    monkeypatch.setenv("TIMELESS_GOOGLE_TOKEN_FILE", str(tmp_path / "oauth.json"))
    store = Store(str(tmp_path / "db.sqlite"))
    yield GoogleSheets(store), store
    store.close()


def test_authorization_uses_state_pkce_and_minimal_scope(integration):
    google, _ = integration
    url = google.authorization_url()
    query = parse_qs(urlparse(url).query)
    assert query["scope"] == ["https://www.googleapis.com/auth/spreadsheets"]
    assert query["code_challenge_method"] == ["S256"]
    assert query["state"][0]


def test_callback_state_is_single_use(integration):
    google, _ = integration
    query = parse_qs(urlparse(google.authorization_url()).query)
    state = query["state"][0]

    def handler(request):
        assert request.url == httpx.URL("https://oauth2.googleapis.com/token")
        return httpx.Response(200, json={"access_token": "access", "refresh_token": "refresh", "expires_in": 3600})

    google.client = httpx.Client(transport=httpx.MockTransport(handler))
    google.complete_authorization("code", state)
    assert google.status()["connected"] is True
    assert google.token_file.stat().st_mode & 0o777 == 0o600
    with pytest.raises(GoogleSheetsError, match="expired"):
        google.complete_authorization("code", state)


def test_publish_creates_then_updates_same_sheet(integration):
    google, store = integration
    google._write_tokens({"access_token": "access", "refresh_token": "refresh", "expires_at": 9999999999})
    requests = []

    def handler(request):
        requests.append((request.method, str(request.url)))
        if request.method == "POST" and str(request.url) == "https://sheets.googleapis.com/v4/spreadsheets":
            return httpx.Response(200, json={"spreadsheetId": "sheet-123"})
        return httpx.Response(200, json={})

    google.client = httpx.Client(transport=httpx.MockTransport(handler))
    opp = store.upsert_opportunity(url="https://example.com/1", company="Acme", role="Intern")
    first = google.publish([opp])
    second = google.publish([opp])
    assert first["rows"] == 1
    assert second["spreadsheet_id"] == "sheet-123"
    assert sum(1 for method, url in requests if method == "POST" and url == "https://sheets.googleapis.com/v4/spreadsheets") == 1


def test_publish_rejects_concurrent_sync(integration):
    google, _ = integration
    assert google._sync_lock.acquire(blocking=False)
    try:
        with pytest.raises(GoogleSheetsError, match="already running"):
            google.publish([])
    finally:
        google._sync_lock.release()
