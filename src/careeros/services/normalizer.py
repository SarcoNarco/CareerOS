from __future__ import annotations

import re
from dataclasses import dataclass

from careeros.db.models.internship import WorkMode
from careeros.schemas.internship import ManualPostingPayload


_WHITESPACE_RE = re.compile(r"\s+")
_REMOTE_TERMS = {"remote", "work from home", "wfh", "worldwide remote"}
_HYBRID_TERMS = {"hybrid"}
_ONSITE_TERMS = {"onsite", "on-site", "office"}


@dataclass(slots=True)
class NormalizedPosting:
    title: str
    normalized_title: str
    location_text: str | None
    normalized_location: str | None
    work_mode: WorkMode


def normalize_posting(payload: ManualPostingPayload) -> NormalizedPosting:
    location_text = _clean_optional(payload.location)
    return NormalizedPosting(
        title=_clean_text(payload.title),
        normalized_title=normalize_title(payload.title),
        location_text=location_text,
        normalized_location=normalize_location(location_text),
        work_mode=normalize_work_mode(payload.work_mode, location_text),
    )


def normalize_title(title: str) -> str:
    cleaned = _clean_text(title).lower()
    cleaned = re.sub(r"\b(internship|intern)\b", "intern", cleaned)
    cleaned = cleaned.replace("software development", "software engineering")
    return _clean_text(cleaned)


def normalize_location(location: str | None) -> str | None:
    if location is None:
        return None
    cleaned = _clean_text(location).lower()
    if any(term in cleaned for term in _REMOTE_TERMS):
        return "remote"
    return cleaned.title()


def normalize_work_mode(work_mode: str | None, location: str | None) -> WorkMode:
    combined = " ".join(part for part in (work_mode, location) if part).lower()
    if any(term in combined for term in _REMOTE_TERMS):
        return WorkMode.REMOTE
    if any(term in combined for term in _HYBRID_TERMS):
        return WorkMode.HYBRID
    if any(term in combined for term in _ONSITE_TERMS):
        return WorkMode.ONSITE
    return WorkMode.UNKNOWN


def _clean_optional(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = _clean_text(value)
    return cleaned or None


def _clean_text(value: str) -> str:
    return _WHITESPACE_RE.sub(" ", value).strip()
