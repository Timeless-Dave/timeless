#!/usr/bin/env python3
"""Forward ActivityWatch web/window events into Timeless (Mac or phone)."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
import urllib.parse
from datetime import datetime, timedelta, timezone

AW = os.environ.get("AW_URL", "http://127.0.0.1:5600").rstrip("/")
TIMLESS = os.environ.get("TIMELESS_URL", "http://127.0.0.1:8787")
SENSOR = os.environ.get("AW_SENSOR", "mac_aw")


def get(url: str):
    if not url.endswith("/") and "/events" not in url:
        url = url + "/"
    with urllib.request.urlopen(url, timeout=8) as r:
        return json.load(r)


def post(url: str, payload: dict) -> None:
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=8) as r:
        r.read()


def events_for(bucket: str, start: datetime) -> list:
    start_s = start.strftime("%Y-%m-%dT%H:%M:%SZ")
    end_s = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        return get(f"{AW}/api/0/buckets/{bucket}/events?start={start_s}&end={end_s}&limit=80")
    except urllib.error.HTTPError:
        return []


def main() -> None:
    since = datetime.now(timezone.utc) - timedelta(minutes=30)
    phone = SENSOR.startswith("phone")
    try:
        bmap = get(f"{AW}/api/0/buckets")
    except Exception as exc:
        print(f"activitywatch unreachable: {exc}")
        try:
            post(
                f"{TIMLESS}/api/heartbeat",
                {"sensor": SENSOR, "detail": f"AW HTTP failed: {exc}"},
            )
        except Exception:
            pass
        return
    post(f"{TIMLESS}/api/heartbeat", {"sensor": SENSOR, "detail": f"{len(bmap)} buckets"})
    names = " ".join(bmap)
    if not phone:
        web_n = sum(1 for k in bmap if "web" in k.lower() or "chrome" in k.lower() or "browser" in k.lower())
        post(
            f"{TIMLESS}/api/heartbeat",
            {
                "sensor": "mac_browser",
                "detail": f"{web_n} web buckets" if web_n else "no Web Watcher bucket (install the Chrome extension)",
            },
        )
    urls = 0
    apps = 0
    for bid, meta in bmap.items():
        btype = str((meta or {}).get("type") or "")
        name = bid.lower() + " " + btype.lower()
        if "unlock" in name:
            continue
        interesting = any(k in name for k in ("web", "window", "currentwindow", "browser", "android", "chrome"))
        if not interesting:
            continue
        for ev in events_for(bid, since):
            data = ev.get("data") or {}
            url = data.get("url") or ""
            title = data.get("title") or data.get("app") or ""
            package = data.get("package") or data.get("app") or ""
            try:
                host = urllib.parse.urlparse(url).netloc.lower() if url else ""
                post(
                    f"{TIMLESS}/api/activity",
                    {
                        "source": SENSOR,
                        "source_id": f"{bid}:{ev.get('id') or ev.get('timestamp') or ev.get('time')}",
                        "ts": ev.get("timestamp") or ev.get("time") or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                        "duration_seconds": float(ev.get("duration") or 0),
                        "app": str(package)[:120],
                        "host": host[:200],
                        "title": str(title)[:240],
                    },
                )
            except Exception as exc:
                print(f"activity ingest failed: {exc}")
            if url:
                try:
                    payload = {"url": url, "title": title or url}
                    if phone:
                        payload["source"] = "phone"
                    post(f"{TIMLESS}/api/ingest/url", payload)
                    urls += 1
                except Exception as exc:
                    print(f"url ingest failed: {exc}")
                    return
            elif package or title:
                try:
                    if phone or "android" in name:
                        post(
                            f"{TIMLESS}/api/ingest/phone",
                            {"summary": f"{title} {package}".strip(), "payload": data},
                        )
                    else:
                        post(f"{TIMLESS}/api/heartbeat", {"sensor": SENSOR, "detail": title})
                    apps += 1
                except Exception as exc:
                    print(f"app ingest failed: {exc}")
                    return
    print(f"forwarded {urls} urls, {apps} app events from {SENSOR} ({names})")


if __name__ == "__main__":
    main()
