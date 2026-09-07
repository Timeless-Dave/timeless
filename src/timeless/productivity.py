from __future__ import annotations

import re
from collections import defaultdict
from datetime import datetime

from timeless.clock import zone
from typing import Any
from urllib.parse import urlparse


STUDY = re.compile(r"\b(?:study|course|lecture|homework|assignment|canvas|blackboard|coursera|edx|leetcode|algorithm|algorithms|textbook|quiz|exam|research|paper|arxiv|scholar|calculus)\b", re.I)
DEVELOPMENT = re.compile(r"\b(?:code|coding|program|develop|debug|github|gitlab|stackoverflow|terminal|xcode|visual studio|vscode|pycharm|documentation|docs)\b", re.I)
APPLICATIONS = re.compile(r"\b(?:job|career|intern|application|apply|resume|cover letter|greenhouse|lever|workday|linkedin jobs)\b", re.I)
MEETINGS = re.compile(r"\b(?:zoom|google meet|microsoft teams|webex|meeting|interview)\b", re.I)
COMMUNICATION = re.compile(r"\b(?:mail|email|gmail|outlook|slack)\b", re.I)
DISTRACTING = re.compile(r"\b(?:netflix|tiktok|instagram|facebook|youtube|reddit|twitch|steam|hulu|disney\+|prime video)\b", re.I)
WORK_OVERRIDE = re.compile(r"\b(?:tutorial|lecture|course|documentation|study|research|interview|application|coding|programming)\b", re.I)
STOP = {"about", "after", "before", "from", "have", "into", "that", "the", "this", "today", "with", "will", "what", "your", "done", "means", "work"}


def classify_activity(app: str | None, title: str | None, host: str | None) -> tuple[str, str]:
    text = " ".join(x for x in (app, title, host) if x)
    if STUDY.search(text):
        return "study", "productive"
    if APPLICATIONS.search(text):
        return "applications", "productive"
    if DEVELOPMENT.search(text):
        return "development", "productive"
    if MEETINGS.search(text):
        return "meeting", "productive"
    if COMMUNICATION.search(text):
        return "communication", "productive"
    if DISTRACTING.search(text) and not WORK_OVERRIDE.search(text):
        return "distraction", "distracting"
    return "other", "neutral"


def humanize_title(text: str) -> str:
    """A readable name for an observed item.

    Window titles and phone events arrive as URLs and reverse-DNS bundle ids;
    neither belongs in a recap the owner reads, so they are reduced to the part
    that means something.
    """
    value = (text or "").strip()
    if not value:
        return "something"
    if "://" in value:
        host = urlparse(value).netloc.replace("www.", "")
        return host or value[:48]
    parts = value.split(".")
    if len(parts) >= 3 and parts[0] in {"com", "org", "net", "io", "app"}:
        return parts[-1].replace("_", " ").replace("-", " ")
    tokens = value.split()
    if len(tokens) >= 2 and "." in tokens[1] and tokens[1].count(".") >= 2:
        return tokens[0]
    return value[:56]


def _tokens(text: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9]+", (text or "").lower()) if len(token) >= 4 and token not in STOP}


def _without_overlaps(samples: list[dict[str, Any]]) -> list[dict[str, Any]]:
    intervals = []
    fallback = []
    for sample in samples:
        try:
            start = datetime.fromisoformat(str(sample.get("ts") or "").replace("Z", "+00:00")).timestamp()
            duration = max(0.0, min(float(sample.get("duration_seconds") or 0), 1800.0))
        except (ValueError, TypeError):
            fallback.append(sample)
            continue
        if duration > 0:
            intervals.append((start, start + duration, sample))
    if not intervals:
        return samples
    boundaries = sorted({point for start, end, _ in intervals for point in (start, end)})
    merged = []
    for left, right in zip(boundaries, boundaries[1:]):
        active = [sample for start, end, sample in intervals if start < right and end > left]
        if not active:
            continue
        def priority(sample):
            specific = sample.get("category") not in {None, "other"}
            web = "web" in str(sample.get("source_id") or "").lower() or bool(sample.get("host"))
            return (int(specific), int(web))
        chosen = dict(max(active, key=priority))
        chosen["duration_seconds"] = right - left
        merged.append(chosen)
    return merged + fallback


def productivity_summary(
    samples: list[dict[str, Any]],
    plan: dict[str, Any] | None,
    corrections: dict[str, str] | None = None,
) -> dict[str, Any]:
    plan_text = " ".join([str((plan or {}).get("outcomes") or "")] + [str(b.get("task") or "") for b in ((plan or {}).get("timeline") or [])])
    plan_tokens = _tokens(plan_text)
    planned_categories = {category for category, pattern in (("study", STUDY), ("applications", APPLICATIONS), ("development", DEVELOPMENT), ("meeting", MEETINGS), ("communication", COMMUNICATION)) if pattern.search(plan_text)}
    corrections = corrections or {}
    goal_windows = _goal_windows(plan)
    goal_minutes: dict[int, float] = defaultdict(float)
    buckets: dict[str, float] = defaultdict(float)
    categories: dict[str, float] = defaultdict(float)
    evidence_minutes: dict[tuple[str, str, str], float] = defaultdict(float)
    corrected_titles: set[str] = set()
    for sample in _without_overlaps(samples):
        minutes = max(0.0, min(float(sample.get("duration_seconds") or 0) / 60.0, 30.0))
        if minutes <= 0:
            continue
        category = str(sample.get("category") or "other")
        productivity = str(sample.get("productivity") or "neutral")
        actual_tokens = _tokens(" ".join(str(sample.get(k) or "") for k in ("title", "app", "host")))
        aligned = bool(plan_tokens and actual_tokens & plan_tokens) or category in planned_categories
        if productivity == "productive" and aligned:
            bucket = "aligned"
        elif productivity == "productive":
            bucket = "productive_off_plan"
        elif productivity == "distracting":
            bucket = "distracting"
        else:
            bucket = "unknown"
        title = str(sample.get("title") or sample.get("host") or sample.get("app") or category)
        # An explicit ruling from the owner outranks the keyword guess.
        if title in corrections:
            bucket = corrections[title]
            corrected_titles.add(title)
        buckets[bucket] += minutes
        categories[category] += minutes
        evidence_minutes[(title, category, bucket)] += minutes
        goal_id = _goal_for_sample(sample, goal_windows)
        if goal_id is not None:
            goal_minutes[goal_id] += minutes
    tracked = sum(buckets.values())
    judged = buckets["aligned"] + buckets["productive_off_plan"] + buckets["distracting"]
    score = round(100 * (buckets["aligned"] + 0.55 * buckets["productive_off_plan"]) / judged) if judged else None
    alignment = round(100 * buckets["aligned"] / (buckets["aligned"] + buckets["productive_off_plan"])) if buckets["aligned"] + buckets["productive_off_plan"] else None
    top = sorted(categories.items(), key=lambda item: -item[1])[:4]
    evidence = [
        {
            # `title` is the stable key a correction is stored against; `label`
            # is what a person should be shown.
            "title": key[0],
            "label": humanize_title(key[0]),
            "category": key[1],
            "bucket": key[2],
            "minutes": round(value),
            "corrected": key[0] in corrected_titles,
        }
        for key, value in evidence_minutes.items()
    ]
    unknown_share = buckets["unknown"] / tracked if tracked else 0.0
    coverage = "low" if tracked < 30 else "medium" if tracked < 120 else "high"
    return {
        "score": score,
        "alignment": alignment,
        "tracked_minutes": round(tracked),
        # The score's denominator: unknown time is deliberately excluded from it,
        # so publish both numbers rather than letting a bare percentage imply
        # the whole day was measured.
        "judged_minutes": round(judged),
        "unknown_share": round(unknown_share, 3),
        "coverage": coverage,
        "confidence": _confidence(tracked, unknown_share, plan),
        "last_sample_at": _latest_sample(samples),
        "minutes": {key: round(buckets[key]) for key in ("aligned", "productive_off_plan", "distracting", "unknown")},
        "top_categories": [{"category": key, "minutes": round(value)} for key, value in top],
        "evidence": sorted(evidence, key=lambda item: -item["minutes"])[:8],
        "estimated": True,
        # Minutes observed while a block for that goal was scheduled. Weak
        # evidence by construction, so it is reported apart from the buckets.
        "goal_minutes": {str(key): round(value) for key, value in sorted(goal_minutes.items())},
        "corrections": len(corrected_titles),
        "method": "keyword and category match between the plan text and observed activity",
    }


def _goal_windows(plan: dict[str, Any] | None) -> list[tuple[int, int, int]]:
    """(start minute, end minute, goal id) for every block that names a goal."""
    windows = []
    for block in (plan or {}).get("timeline") or []:
        goal_id = block.get("goal_id")
        if goal_id is None:
            continue
        start = _minutes_of_day(block.get("start"))
        end = _minutes_of_day(block.get("end"))
        if start is None or end is None or end <= start:
            continue
        windows.append((start, end, int(goal_id)))
    return windows


def _goal_for_sample(sample: dict[str, Any], windows: list[tuple[int, int, int]]) -> int | None:
    if not windows:
        return None
    try:
        stamp = datetime.fromisoformat(str(sample.get("ts") or "").replace("Z", "+00:00"))
    except ValueError:
        return None
    local = stamp.astimezone(zone())
    minute = local.hour * 60 + local.minute
    for start, end, goal_id in windows:
        if start <= minute < end:
            return goal_id
    return None


def _minutes_of_day(value: Any) -> int | None:
    match = re.match(r"^(\d{1,2}):(\d{2})$", str(value or "").strip())
    if not match:
        return None
    hours, minutes = int(match.group(1)), int(match.group(2))
    return hours * 60 + minutes if hours <= 23 and minutes <= 59 else None


def _confidence(tracked: float, unknown_share: float, plan: dict[str, Any] | None) -> str:
    """How much weight the estimate can bear.

    Keyword matching against a thin plan, a short sample, or a large slice of
    unclassifiable time all mean the same thing: do not read the score as a verdict.
    Corrections need no special case here: ruling on an item moves its minutes out
    of `unknown`, so a corrected day earns its confidence from the evidence itself.
    """
    if not plan or tracked < 30 or unknown_share > 0.4:
        return "low"
    if tracked < 120 or unknown_share > 0.2:
        return "medium"
    return "high"


def _latest_sample(samples: list[dict[str, Any]]) -> str | None:
    stamps = [str(sample.get("ts")) for sample in samples if sample.get("ts")]
    return max(stamps) if stamps else None
