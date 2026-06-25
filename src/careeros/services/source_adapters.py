from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from html import unescape
from typing import Any, Callable, Protocol
from urllib import error, request

from pydantic import HttpUrl
from sqlalchemy import select
from sqlalchemy.orm import Session

from careeros.db.base import utc_now
from careeros.db.models.internship import (
    InternshipSource,
    SourcePolicy,
    SourcePolicyStatus,
    SourceType,
)
from careeros.schemas.internship import ManualPostingPayload
from careeros.services.ingestion_service import (
    AdapterPosting,
    IngestionOutcome,
    ingest_adapter_postings,
)


FetchJson = Callable[[str, dict[str, str], int], dict[str, Any]]
_ENTRY_LEVEL_TERMS = (
    "intern",
    "internship",
    "junior",
    "entry level",
    "entry-level",
    "graduate",
    "new grad",
    "trainee",
    "associate",
    "student",
    "working student",
)
_SENIORITY_EXCLUSION_TERMS = (
    "senior",
    "sr.",
    "sr ",
    "staff",
    "principal",
    "lead",
    "manager",
    "director",
    "head of",
    "head ",
    "vp ",
    "vice president",
    "teamleiter",
    "leitung",
    "leiter",
)
_TECH_RELEVANCE_TERMS = (
    "ai",
    "api",
    "backend",
    "cloud",
    "data",
    "developer",
    "devops",
    "engineer",
    "engineering",
    "frontend",
    "full stack",
    "full-stack",
    "javascript",
    "machine learning",
    "ml",
    "platform",
    "postgres",
    "python",
    "react",
    "software",
    "sql",
    "typescript",
)
_YEARS_EXPERIENCE_RE = re.compile(
    r"\b(?:[5-9]|1[0-9])\+?\s*(?:\+?\s*)?(?:years|yrs)\b|\b(?:[5-9]|1[0-9])\+\s*(?:years|yrs)?",
    re.IGNORECASE,
)


class SourceAdapterError(RuntimeError):
    """Raised when a source adapter cannot fetch or parse postings safely."""


class SourceAdapter(Protocol):
    name: str
    display_name: str
    source_type: SourceType
    base_url: str
    policy_status: SourcePolicyStatus
    policy_notes: str
    rate_limit_notes: str
    robots_notes: str

    def fetch_postings(self, limit: int | None = None) -> list[AdapterPosting]:
        ...


def _fetch_json(url: str, headers: dict[str, str], timeout_seconds: int) -> dict[str, Any]:
    req = request.Request(url, headers=headers, method="GET")
    try:
        with request.urlopen(req, timeout=timeout_seconds) as response:
            raw_body = response.read().decode("utf-8")
    except error.HTTPError as exc:
        raise SourceAdapterError(f"Source fetch failed with HTTP {exc.code}: {exc.reason}") from exc
    except error.URLError as exc:
        raise SourceAdapterError(f"Source fetch failed: {exc.reason}") from exc

    try:
        parsed = json.loads(raw_body)
    except json.JSONDecodeError as exc:
        raise SourceAdapterError("Source returned invalid JSON.") from exc
    if not isinstance(parsed, dict):
        raise SourceAdapterError("Source returned JSON that was not an object.")
    return parsed


@dataclass(slots=True)
class RemotiveAdapter:
    fetch_json: FetchJson = _fetch_json

    name: str = "remotive"
    display_name: str = "Remotive"
    source_type: SourceType = SourceType.API
    base_url: str = "https://remotive.com/api/remote-jobs?category=software-dev"
    policy_status: SourcePolicyStatus = SourcePolicyStatus.ALLOWED
    policy_notes: str = (
        "Public API-style JSON source. CareerOS fetches a bounded software-dev listing "
        "feed and filters for internship-like postings."
    )
    rate_limit_notes: str = (
        "Manual CLI sync only. Use bounded limits and avoid repeated rapid syncs."
    )
    robots_notes: str = "API-style JSON endpoint; no browser automation or broad scraping."

    def fetch_postings(self, limit: int | None = None) -> list[AdapterPosting]:
        data = self.fetch_json(self.base_url, _polite_headers(self.name), 30)
        jobs = data.get("jobs")
        if not isinstance(jobs, list):
            raise SourceAdapterError("Remotive response did not contain a `jobs` list.")

        postings: list[AdapterPosting] = []
        for raw_job in jobs:
            if not isinstance(raw_job, dict):
                continue
            parsed = _parse_remotive_job(raw_job)
            if parsed is None:
                continue
            postings.append(parsed)
            if limit is not None and len(postings) >= limit:
                break
        return postings


@dataclass(slots=True)
class ArbeitnowAdapter:
    fetch_json: FetchJson = _fetch_json

    name: str = "arbeitnow"
    display_name: str = "Arbeitnow"
    source_type: SourceType = SourceType.API
    base_url: str = "https://www.arbeitnow.com/api/job-board-api"
    policy_status: SourcePolicyStatus = SourcePolicyStatus.ALLOWED
    policy_notes: str = (
        "Public API-style JSON job-board source. CareerOS fetches a bounded listing "
        "feed and filters for internship, junior, and entry-level technical roles."
    )
    rate_limit_notes: str = (
        "Manual CLI sync only. Use bounded limits and avoid repeated rapid syncs."
    )
    robots_notes: str = "API-style JSON endpoint; no browser automation or broad scraping."

    def fetch_postings(self, limit: int | None = None) -> list[AdapterPosting]:
        data = self.fetch_json(self.base_url, _polite_headers(self.name), 30)
        jobs = data.get("data")
        if not isinstance(jobs, list):
            raise SourceAdapterError("Arbeitnow response did not contain a `data` list.")

        postings: list[AdapterPosting] = []
        for raw_job in jobs:
            if not isinstance(raw_job, dict):
                continue
            parsed = _parse_arbeitnow_job(raw_job)
            if parsed is None:
                continue
            postings.append(parsed)
            if limit is not None and len(postings) >= limit:
                break
        return postings


def get_source_adapter(source_name: str) -> SourceAdapter:
    normalized = source_name.strip().casefold()
    if normalized == "remotive":
        return RemotiveAdapter()
    if normalized == "arbeitnow":
        return ArbeitnowAdapter()
    raise SourceAdapterError(f"Unsupported source adapter: {source_name}")


def list_source_adapter_names() -> list[str]:
    return ["arbeitnow", "remotive"]


def sync_source_adapter(
    session: Session,
    source_name: str,
    limit: int | None = None,
    fetch_json: FetchJson | None = None,
) -> IngestionOutcome:
    adapter = get_source_adapter(source_name)
    if fetch_json is not None and isinstance(adapter, RemotiveAdapter):
        adapter = RemotiveAdapter(fetch_json=fetch_json)
    if fetch_json is not None and isinstance(adapter, ArbeitnowAdapter):
        adapter = ArbeitnowAdapter(fetch_json=fetch_json)

    source = ensure_adapter_source(session=session, adapter=adapter)
    postings = adapter.fetch_postings(limit=limit)
    return ingest_adapter_postings(
        session=session,
        source_id=source.id,
        adapter_name=adapter.name,
        postings=postings,
    )


def ensure_adapter_source(session: Session, adapter: SourceAdapter) -> InternshipSource:
    source = session.scalar(
        select(InternshipSource).where(InternshipSource.name == adapter.display_name)
    )
    if source is None:
        source = InternshipSource(
            name=adapter.display_name,
            source_type=adapter.source_type,
            base_url=adapter.base_url,
            is_active=True,
        )
        session.add(source)
        session.flush()
    else:
        source.source_type = adapter.source_type
        source.base_url = adapter.base_url
        source.is_active = True

    if source.policy is None:
        policy = SourcePolicy(
            source=source,
            policy_status=adapter.policy_status,
            robots_checked_at=utc_now(),
            rate_limit_notes=adapter.rate_limit_notes,
            notes=f"{adapter.policy_notes}\n{adapter.robots_notes}",
        )
        session.add(policy)
    else:
        source.policy.policy_status = adapter.policy_status
        source.policy.robots_checked_at = source.policy.robots_checked_at or utc_now()
        source.policy.rate_limit_notes = adapter.rate_limit_notes
        source.policy.notes = f"{adapter.policy_notes}\n{adapter.robots_notes}"

    session.commit()
    session.refresh(source)
    return source


def _parse_remotive_job(raw_job: dict[str, Any]) -> AdapterPosting | None:
    title = _clean_text(str(raw_job.get("title") or ""))
    description = _html_to_text(str(raw_job.get("description") or ""))
    if not title or not _looks_like_entry_level_tech_role(title, description):
        return None

    url = str(raw_job.get("url") or "").strip()
    if not url:
        return None

    company_name = _clean_text(str(raw_job.get("company_name") or "Unknown Company"))
    location = _clean_text(str(raw_job.get("candidate_required_location") or "Remote"))
    external_id = raw_job.get("id")
    tags = raw_job.get("tags") if isinstance(raw_job.get("tags"), list) else []
    category = _clean_text(str(raw_job.get("category") or ""))
    publication_date = _parse_datetime(raw_job.get("publication_date"))

    payload = ManualPostingPayload(
        external_id=f"remotive:{external_id}" if external_id is not None else None,
        source_url=HttpUrl(url),
        title=title,
        company_name=company_name,
        company_domain=None,
        description=description or title,
        requirements=", ".join(str(tag) for tag in tags if tag) or None,
        responsibilities=None,
        application_url=HttpUrl(url),
        location=location or "Remote",
        work_mode="Remote",
        posted_at=publication_date,
        metadata={
            "adapter": "remotive",
            "category": category,
            "tags": tags,
        },
    )
    return AdapterPosting(payload=payload, raw_payload=raw_job)


def _parse_arbeitnow_job(raw_job: dict[str, Any]) -> AdapterPosting | None:
    title = _clean_text(str(raw_job.get("title") or ""))
    description = _html_to_text(str(raw_job.get("description") or ""))
    tags = raw_job.get("tags") if isinstance(raw_job.get("tags"), list) else []
    tag_text = " ".join(str(tag) for tag in tags if tag)
    if not title or not _looks_like_entry_level_tech_role(
        title,
        f"{description} {tag_text}",
        require_title_entry_signal=True,
        require_title_tech_signal=True,
    ):
        return None

    url = str(raw_job.get("url") or "").strip()
    if not url:
        return None

    company_name = _clean_text(str(raw_job.get("company_name") or "Unknown Company"))
    location = _clean_text(str(raw_job.get("location") or "Remote"))
    slug = raw_job.get("slug")
    created_at = _parse_unix_timestamp(raw_job.get("created_at"))
    is_remote = raw_job.get("remote") is True

    payload = ManualPostingPayload(
        external_id=f"arbeitnow:{slug}" if slug is not None else None,
        source_url=HttpUrl(url),
        title=title,
        company_name=company_name,
        company_domain=None,
        description=description or title,
        requirements=", ".join(str(tag) for tag in tags if tag) or None,
        responsibilities=None,
        application_url=HttpUrl(url),
        location=location or "Remote",
        work_mode="Remote" if is_remote else "Unknown",
        posted_at=created_at,
        metadata={
            "adapter": "arbeitnow",
            "tags": tags,
            "job_types": raw_job.get("job_types") if isinstance(raw_job.get("job_types"), list) else [],
            "remote": is_remote,
        },
    )
    return AdapterPosting(payload=payload, raw_payload=raw_job)


def _polite_headers(source_name: str) -> dict[str, str]:
    return {
        "Accept": "application/json",
        "User-Agent": f"CareerOS/0.1 local internship sync ({source_name})",
    }


def _looks_like_entry_level_tech_role(
    title: str,
    description: str,
    *,
    require_title_entry_signal: bool = False,
    require_title_tech_signal: bool = False,
) -> bool:
    combined = f"{title} {description}".casefold()
    title_text = title.casefold()
    if any(term in title_text for term in _SENIORITY_EXCLUSION_TERMS):
        return False
    if _YEARS_EXPERIENCE_RE.search(combined):
        return False
    entry_haystack = title_text if require_title_entry_signal else combined
    tech_haystack = title_text if require_title_tech_signal else combined
    has_entry_signal = any(term in entry_haystack for term in _ENTRY_LEVEL_TERMS)
    has_tech_signal = any(term in tech_haystack for term in _TECH_RELEVANCE_TERMS)
    return has_entry_signal and has_tech_signal


def _html_to_text(value: str) -> str:
    without_tags = re.sub(r"<[^>]+>", " ", value)
    return _clean_text(unescape(without_tags))


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _parse_datetime(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    normalized = value.strip().replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def _parse_unix_timestamp(value: object) -> datetime | None:
    if isinstance(value, int):
        return datetime.fromtimestamp(value, tz=timezone.utc)
    return _parse_datetime(value)
