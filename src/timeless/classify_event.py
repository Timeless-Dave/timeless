from __future__ import annotations

import re

JOIN_RE = re.compile(r"zoom\.us|meet\.google|teams\.microsoft|webex\.com|gotomeeting", re.I)
HACK_RE = re.compile(r"hackathon|\bctf\b|devfest|hack night", re.I)
CONF_RE = re.compile(r"conference|summit|symposium|\bmeetup\b", re.I)
SUBMIT_RE = re.compile(r"deadline|submit by|applications? close|submission", re.I)
PRESENT_RE = re.compile(r"\bdemo\b|\bpitch\b|presentation|judging", re.I)
TIMELESS_KIND_RE = re.compile(r"Timeless kind:\s*(course|deadline|calendar_note)", re.I)
URL_RE = re.compile(r"https?://[^\s<>\"']+", re.I)


def is_join_url(url: str | None) -> bool:
    return bool(url and JOIN_RE.search(url))


def pick_join_url(*blobs: str | None, preferred: str | None = None) -> str | None:
    if is_join_url(preferred):
        return preferred.rstrip(").,")
    text = " ".join(x for x in (preferred, *blobs) if x)
    for m in URL_RE.finditer(text):
        url = m.group(0).rstrip(").,")
        if is_join_url(url):
            return url
    return None


def mail_matches_event(title: str, subject: str) -> bool:
    t = (title or "").lower().strip()
    s = (subject or "").lower().strip()
    if not t or not s:
        return False
    shorter, longer = (t, s) if len(t) <= len(s) else (s, t)
    if len(shorter) >= 8 and shorter in longer:
        return True
    words = [w for w in re.findall(r"[a-z0-9]+", t) if len(w) >= 4]
    return bool(words) and all(w in s for w in words)


def classify_event(title: str, join_url: str | None, location: str | None, notes: str | None = None) -> tuple[str, str]:
    blob = " ".join(x for x in (title, notes, location, join_url) if x)
    kind = "meeting"
    marker = TIMELESS_KIND_RE.search(blob)
    if marker:
        kind = marker.group(1).lower()
    elif HACK_RE.search(blob):
        kind = "hackathon"
    elif CONF_RE.search(blob):
        kind = "conference"
    picked = pick_join_url(notes, location, preferred=join_url)
    if picked or JOIN_RE.search(blob):
        modality = "virtual"
    elif (location or "").strip():
        modality = "physical"
    else:
        modality = "virtual"
    return kind, modality


def looks_like_submission(title: str, notes: str | None = None) -> bool:
    return bool(SUBMIT_RE.search(" ".join(x for x in (title, notes) if x)))


def looks_like_presentation(title: str, notes: str | None = None) -> bool:
    return bool(PRESENT_RE.search(" ".join(x for x in (title, notes) if x)))
