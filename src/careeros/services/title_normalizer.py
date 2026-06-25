from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from careeros.db.models.internship import NormalizedTitle, TitleAlias


_WHITESPACE_RE = re.compile(r"\s+")


def normalize_title_to_record(session: Session, raw_title: str) -> NormalizedTitle:
    cleaned = _clean(raw_title)

    exact_alias = session.scalar(
        select(TitleAlias)
        .options(selectinload(TitleAlias.normalized_title))
        .where(TitleAlias.alias == cleaned)
    )
    if exact_alias is not None:
        return exact_alias.normalized_title

    alias_match = session.scalar(
        select(TitleAlias)
        .options(selectinload(TitleAlias.normalized_title))
        .where(TitleAlias.alias.contains(cleaned) | TitleAlias.alias.op("LIKE")(f"%{cleaned}%"))
    )
    if alias_match is not None:
        return alias_match.normalized_title

    if any(term in cleaned for term in ("machine learning", " ml ", " ai ", "artificial intelligence")):
        return _get_title(session=session, canonical_title="ML")
    if "data" in cleaned or "analyst" in cleaned:
        return _get_title(session=session, canonical_title="Data")
    if any(term in cleaned for term in ("software", "backend", "frontend", "sde", "developer")):
        return _get_title(session=session, canonical_title="SWE")
    return _get_title(session=session, canonical_title="Other")


def _get_title(session: Session, canonical_title: str) -> NormalizedTitle:
    title = session.scalar(
        select(NormalizedTitle).where(NormalizedTitle.canonical_title == canonical_title)
    )
    if title is None:
        raise RuntimeError(f"Missing normalized title seed: {canonical_title}")
    return title


def _clean(title: str) -> str:
    normalized = _WHITESPACE_RE.sub(" ", title.casefold().strip())
    normalized = normalized.replace("internship", "intern")
    return _WHITESPACE_RE.sub(" ", normalized).strip()
