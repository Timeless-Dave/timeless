from __future__ import annotations

import re
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

JOB_HOST_MARKERS = (
    "greenhouse.io",
    "lever.co",
    "myworkdayjobs.com",
    "workday.com",
    "ashbyhq.com",
    "icims.com",
    "smartrecruiters.com",
    "jobvite.com",
    "taleo.net",
    "boards.eu.greenhouse.io",
    "linkedin.com/jobs",
    "indeed.com",
    "wellfound.com",
    "glassdoor.com",
    "careers.",
    "/careers",
    "/jobs/",
)

HACKATHON_HOSTS = ("devpost.com", "mlh.io", "hackerearth.com", "devfolio.co")
CONFERENCE_HOSTS = ("sessionize.com", "papercall.io", "cvent.com")
TRACKING_QUERY_KEYS = {"utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "ref", "refid", "source", "trk"}

CONFIRMATION_PHRASES = (
    "thank you for applying",
    "application received",
    "application submitted",
    "we have received your application",
    "successfully applied",
)

REQUIREMENT_MISS_PHRASES = (
    "years of experience required",
    "must have",
    "you do not meet",
    "minimum qualifications",
    "not eligible",
)


def looks_like_job_url(url: str) -> bool:
    raw = (url or "").lower()
    if not raw.startswith("http"):
        return False
    return any(marker in raw for marker in JOB_HOST_MARKERS)


def canonicalize_program_url(url: str) -> str:
    try:
        parsed = urlparse((url or "").strip())
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            return url
        query = [(k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True) if k.lower() not in TRACKING_QUERY_KEYS and not k.lower().startswith("utm_")]
        path = parsed.path.rstrip("/") or "/"
        return urlunparse((parsed.scheme.lower(), parsed.netloc.lower(), path, "", urlencode(query), ""))
    except ValueError:
        return url


def program_kind_for_url(url: str, title: str | None = None) -> str | None:
    raw = f"{url or ''} {title or ''}".lower()
    host = host_of(url)
    if looks_like_job_url(url):
        return "internship"
    if any(domain in host for domain in HACKATHON_HOSTS) or re.search(r"\bhackathon\b|\bctf\b|hack\s+(?:night|week)", raw):
        return "hackathon"
    if any(domain in host for domain in CONFERENCE_HOSTS) or re.search(r"\bconference\b|\bsummit\b|\bsymposium\b", raw):
        return "conference"
    return None


def host_of(url: str) -> str:
    try:
        return urlparse(url).netloc.lower()
    except Exception:
        return ""


def classify_screen_text(text: str) -> str | None:
    blob = (text or "").lower()
    if any(p in blob for p in CONFIRMATION_PHRASES):
        return "confirmation"
    if any(p in blob for p in REQUIREMENT_MISS_PHRASES):
        return "requirement_miss"
    return None
