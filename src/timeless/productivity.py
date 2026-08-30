from __future__ import annotations

import re
from collections import defaultdict
from datetime import datetime
from typing import Any


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


def productivity_summary(samples: list[dict[str, Any]], plan: dict[str, Any] | None) -> dict[str, Any]:
    plan_text = " ".join([str((plan or {}).get("outcomes") or "")] + [str(b.get("task") or "") for b in ((plan or {}).get("timeline") or [])])
    plan_tokens = _tokens(plan_text)
    planned_categories = {category for category, pattern in (("study", STUDY), ("applications", APPLICATIONS), ("development", DEVELOPMENT), ("meeting", MEETINGS), ("communication", COMMUNICATION)) if pattern.search(plan_text)}
    buckets: dict[str, float] = defaultdict(float)
    categories: dict[str, float] = defaultdict(float)
    evidence_minutes: dict[tuple[str, str, str], float] = defaultdict(float)
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
        buckets[bucket] += minutes
        categories[category] += minutes
        evidence_key = (str(sample.get("title") or sample.get("host") or sample.get("app") or category), category, bucket)
        evidence_minutes[evidence_key] += minutes
    tracked = sum(buckets.values())
    judged = buckets["aligned"] + buckets["productive_off_plan"] + buckets["distracting"]
    score = round(100 * (buckets["aligned"] + 0.55 * buckets["productive_off_plan"]) / judged) if judged else None
    alignment = round(100 * buckets["aligned"] / (buckets["aligned"] + buckets["productive_off_plan"])) if buckets["aligned"] + buckets["productive_off_plan"] else None
    top = sorted(categories.items(), key=lambda item: -item[1])[:4]
    evidence = [{"title": key[0], "category": key[1], "bucket": key[2], "minutes": round(value)} for key, value in evidence_minutes.items()]
    return {
        "score": score,
        "alignment": alignment,
        "tracked_minutes": round(tracked),
        "coverage": "low" if tracked < 30 else "medium" if tracked < 120 else "high",
        "minutes": {key: round(buckets[key]) for key in ("aligned", "productive_off_plan", "distracting", "unknown")},
        "top_categories": [{"category": key, "minutes": round(value)} for key, value in top],
        "evidence": sorted(evidence, key=lambda item: -item["minutes"])[:8],
        "estimated": True,
    }
