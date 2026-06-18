from __future__ import annotations

import hashlib
import json
from urllib.parse import urlsplit, urlunsplit

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from careeros.db.models.internship import Internship
from careeros.schemas.internship import ManualPostingPayload
from careeros.services.normalizer import NormalizedPosting


def compute_content_hash(payload_json: dict[str, object]) -> str:
    canonical = json.dumps(payload_json, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def compute_dedupe_key(payload: ManualPostingPayload, normalized: NormalizedPosting) -> str:
    if payload.source_url is not None:
        return f"url:{_normalize_url(str(payload.source_url))}"
    if payload.external_id:
        return f"external:{payload.external_id.strip().lower()}"

    company = payload.company_name.strip().lower()
    title = normalized.normalized_title.lower()
    location = (normalized.normalized_location or "").strip().lower()
    return f"fallback:{company}:{title}:{location}"


def find_duplicate_internship(
    session: Session,
    source_id: object,
    dedupe_key: str,
    content_hash: str,
) -> Internship | None:
    return session.scalar(
        select(Internship).where(
            Internship.source_id == source_id,
            or_(
                Internship.dedupe_key == dedupe_key,
                Internship.content_hash == content_hash,
            ),
        )
    )


def _normalize_url(url: str) -> str:
    parts = urlsplit(url)
    netloc = parts.netloc.lower()
    path = parts.path.rstrip("/")
    return urlunsplit((parts.scheme.lower(), netloc, path, "", ""))
