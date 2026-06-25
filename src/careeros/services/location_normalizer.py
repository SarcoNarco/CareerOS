from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from careeros.db.models.internship import NormalizedLocation, WorkMode


_REMOTE_TERMS = ("remote", "work from home", "wfh", "worldwide")
_HYBRID_TERMS = ("hybrid",)
_ONSITE_TERMS = ("onsite", "on-site", "office")


def normalize_location_to_record(
    session: Session,
    location_text: str | None,
    work_mode_text: str | None,
) -> NormalizedLocation:
    work_mode = normalize_work_mode(location_text=location_text, work_mode_text=work_mode_text)
    return _get_location(session=session, work_mode=work_mode)


def normalize_work_mode(location_text: str | None, work_mode_text: str | None) -> WorkMode:
    combined = " ".join(part for part in (location_text, work_mode_text) if part).casefold()
    if any(term in combined for term in _REMOTE_TERMS):
        return WorkMode.REMOTE
    if any(term in combined for term in _HYBRID_TERMS):
        return WorkMode.HYBRID
    if any(term in combined for term in _ONSITE_TERMS):
        return WorkMode.ONSITE
    return WorkMode.UNKNOWN


def _get_location(session: Session, work_mode: WorkMode) -> NormalizedLocation:
    label_by_mode = {
        WorkMode.REMOTE: "Remote",
        WorkMode.HYBRID: "Hybrid",
        WorkMode.ONSITE: "Onsite",
        WorkMode.UNKNOWN: "Unknown",
    }
    location = session.scalar(
        select(NormalizedLocation).where(
            NormalizedLocation.canonical_label == label_by_mode[work_mode]
        )
    )
    if location is None:
        raise RuntimeError(f"Missing normalized location seed: {label_by_mode[work_mode]}")
    return location
