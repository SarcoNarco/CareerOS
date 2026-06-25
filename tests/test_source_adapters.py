from __future__ import annotations

from sqlalchemy import select

from careeros.db.models.internship import (
    Internship,
    InternshipSource,
    RawPosting,
    SourcePolicy,
    SourceType,
)
from careeros.services.source_adapters import ArbeitnowAdapter, RemotiveAdapter, sync_source_adapter


def _remotive_payload() -> dict[str, object]:
    return {
        "jobs": [
            {
                "id": 101,
                "url": "https://remotive.com/remote-jobs/software-dev/ml-intern-101",
                "title": "Machine Learning Intern",
                "company_name": "Remote AI Lab",
                "candidate_required_location": "Worldwide",
                "description": "<p>Internship building Python and PyTorch models.</p>",
                "tags": ["python", "pytorch", "machine learning"],
                "category": "Software Development",
                "publication_date": "2026-06-20T12:00:00Z",
            },
            {
                "id": 102,
                "url": "https://remotive.com/remote-jobs/software-dev/backend-engineer-102",
                "title": "Senior Backend Engineer",
                "company_name": "Remote Systems",
                "candidate_required_location": "Worldwide",
                "description": "<p>Build backend APIs. Requires 7+ years of experience.</p>",
                "tags": ["python", "fastapi"],
                "category": "Software Development",
            },
            {
                "id": 103,
                "url": "https://remotive.com/remote-jobs/software-dev/junior-data-analyst-103",
                "title": "Junior Data Analyst",
                "company_name": "Remote Data Co",
                "candidate_required_location": "Worldwide",
                "description": "<p>Entry-level role using Python, SQL, and pandas.</p>",
                "tags": ["python", "sql", "pandas"],
                "category": "Data",
            },
            {
                "id": 104,
                "url": "https://remotive.com/remote-jobs/software-dev/staff-product-engineer-104",
                "title": "Staff Product Engineer",
                "company_name": "Remote Staff Co",
                "candidate_required_location": "Worldwide",
                "description": "<p>Staff role for product engineering leadership.</p>",
                "tags": ["python"],
                "category": "Software Development",
            },
        ]
    }


def _fake_fetch_json(url: str, headers: dict[str, str], timeout_seconds: int) -> dict[str, object]:
    assert "remotive.com" in url
    assert headers["Accept"] == "application/json"
    assert "CareerOS" in headers["User-Agent"]
    assert timeout_seconds == 30
    return _remotive_payload()


def _arbeitnow_payload() -> dict[str, object]:
    return {
        "data": [
            {
                "slug": "junior-python-developer",
                "title": "Junior Python Developer",
                "company_name": "Arbeit AI",
                "location": "Remote",
                "remote": True,
                "url": "https://www.arbeitnow.com/jobs/junior-python-developer",
                "description": "<p>Entry-level role using Python, SQL, FastAPI, and Docker.</p>",
                "tags": ["python", "sql", "fastapi", "docker"],
                "job_types": ["full-time"],
                "created_at": 1782240000,
            },
            {
                "slug": "machine-learning-intern",
                "title": "Machine Learning Intern",
                "company_name": "Arbeit ML",
                "location": "Worldwide",
                "remote": True,
                "url": "https://www.arbeitnow.com/jobs/machine-learning-intern",
                "description": "<p>Internship with Python, Machine Learning, PyTorch, and Pandas.</p>",
                "tags": ["python", "machine learning", "pytorch", "pandas"],
                "job_types": ["internship"],
                "created_at": 1782243600,
            },
            {
                "slug": "senior-platform-engineer",
                "title": "Senior Platform Engineer",
                "company_name": "Arbeit Senior",
                "location": "Remote",
                "remote": True,
                "url": "https://www.arbeitnow.com/jobs/senior-platform-engineer",
                "description": "<p>Requires 8+ years of platform engineering experience.</p>",
                "tags": ["python"],
                "job_types": ["full-time"],
                "created_at": 1782247200,
            },
            {
                "slug": "staff-data-engineer",
                "title": "Staff Data Engineer",
                "company_name": "Arbeit Staff",
                "location": "Remote",
                "remote": True,
                "url": "https://www.arbeitnow.com/jobs/staff-data-engineer",
                "description": "<p>Staff role for data platform leadership.</p>",
                "tags": ["python", "sql"],
                "job_types": ["full-time"],
                "created_at": 1782250800,
            },
            {
                "slug": "founders-associate-marketing",
                "title": "Founders Associate / Marketing & Growth",
                "company_name": "Arbeit Marketing",
                "location": "Remote",
                "remote": True,
                "url": "https://www.arbeitnow.com/jobs/founders-associate-marketing",
                "description": "<p>Associate role for marketing and growth operations.</p>",
                "tags": ["marketing", "growth"],
                "job_types": ["full-time"],
                "created_at": 1782254400,
            },
            {
                "slug": "working-student-data",
                "title": "Working Student Data Analyst",
                "company_name": "Arbeit Student",
                "location": "Remote",
                "remote": True,
                "url": "https://www.arbeitnow.com/jobs/working-student-data",
                "description": "<p>Student role using SQL, Python, and data analysis.</p>",
                "tags": ["sql", "python", "data"],
                "job_types": ["working-student"],
                "created_at": 1782258000,
            },
        ]
    }


def _fake_arbeitnow_fetch_json(
    url: str,
    headers: dict[str, str],
    timeout_seconds: int,
) -> dict[str, object]:
    assert "arbeitnow.com" in url
    assert headers["Accept"] == "application/json"
    assert "CareerOS" in headers["User-Agent"]
    assert timeout_seconds == 30
    return _arbeitnow_payload()


def test_remotive_adapter_parses_mocked_response() -> None:
    adapter = RemotiveAdapter(fetch_json=_fake_fetch_json)

    postings = adapter.fetch_postings(limit=10)

    assert len(postings) == 2
    posting = postings[0]
    assert posting.payload.title == "Machine Learning Intern"
    assert posting.payload.company_name == "Remote AI Lab"
    assert posting.payload.work_mode == "Remote"
    assert posting.payload.requirements == "python, pytorch, machine learning"
    assert posting.payload.description == "Internship building Python and PyTorch models."
    assert posting.raw_payload["id"] == 101
    assert postings[1].payload.title == "Junior Data Analyst"


def test_sync_source_adapter_creates_policy_raw_posting_and_internship(db_session) -> None:
    outcome = sync_source_adapter(
        session=db_session,
        source_name="remotive",
        limit=10,
        fetch_json=_fake_fetch_json,
    )

    assert outcome.ingestion_run.items_seen == 2
    assert outcome.ingestion_run.items_created == 2
    assert outcome.ingestion_run.metadata_json["adapter"] == "remotive"

    source = db_session.scalar(select(InternshipSource).where(InternshipSource.name == "Remotive"))
    assert source is not None
    assert source.source_type == SourceType.API

    policy = db_session.scalar(select(SourcePolicy).where(SourcePolicy.source_id == source.id))
    assert policy is not None
    assert policy.policy_status == "allowed"
    assert policy.robots_checked_at is not None
    assert policy.rate_limit_notes is not None
    assert "Manual CLI sync" in policy.rate_limit_notes

    raw_postings = list(db_session.scalars(select(RawPosting).where(RawPosting.source_id == source.id)))
    raw_titles = {posting.payload_json["title"] for posting in raw_postings}
    assert raw_titles == {"Machine Learning Intern", "Junior Data Analyst"}

    internships = list(db_session.scalars(select(Internship).where(Internship.source_id == source.id)))
    internship_titles = {internship.title for internship in internships}
    application_urls = {internship.application_url for internship in internships}
    assert internship_titles == {"Machine Learning Intern", "Junior Data Analyst"}
    assert "https://remotive.com/remote-jobs/software-dev/ml-intern-101" in application_urls


def test_sync_source_adapter_prevents_duplicate_internship(db_session) -> None:
    first = sync_source_adapter(
        session=db_session,
        source_name="remotive",
        limit=10,
        fetch_json=_fake_fetch_json,
    )
    second = sync_source_adapter(
        session=db_session,
        source_name="remotive",
        limit=10,
        fetch_json=_fake_fetch_json,
    )

    assert first.ingestion_run.items_created == 2
    assert second.ingestion_run.items_created == 0
    assert second.duplicate_count == 2
    assert len(list(db_session.scalars(select(Internship)))) == 2
    assert len(list(db_session.scalars(select(RawPosting)))) == 4


def test_remotive_adapter_excludes_obvious_senior_roles() -> None:
    adapter = RemotiveAdapter(fetch_json=_fake_fetch_json)

    titles = {posting.payload.title for posting in adapter.fetch_postings(limit=10)}

    assert "Senior Backend Engineer" not in titles
    assert "Staff Product Engineer" not in titles


def test_remotive_adapter_includes_entry_level_roles() -> None:
    adapter = RemotiveAdapter(fetch_json=_fake_fetch_json)

    titles = {posting.payload.title for posting in adapter.fetch_postings(limit=10)}

    assert "Machine Learning Intern" in titles
    assert "Junior Data Analyst" in titles


def test_arbeitnow_adapter_parses_mocked_response() -> None:
    adapter = ArbeitnowAdapter(fetch_json=_fake_arbeitnow_fetch_json)

    postings = adapter.fetch_postings(limit=10)

    assert len(postings) == 3
    titles = {posting.payload.title for posting in postings}
    assert titles == {
        "Junior Python Developer",
        "Machine Learning Intern",
        "Working Student Data Analyst",
    }
    first = postings[0]
    assert first.payload.company_name == "Arbeit AI"
    assert first.payload.work_mode == "Remote"
    assert first.payload.requirements == "python, sql, fastapi, docker"
    assert first.payload.external_id == "arbeitnow:junior-python-developer"
    assert first.raw_payload["slug"] == "junior-python-developer"


def test_arbeitnow_adapter_excludes_obvious_senior_roles() -> None:
    adapter = ArbeitnowAdapter(fetch_json=_fake_arbeitnow_fetch_json)

    titles = {posting.payload.title for posting in adapter.fetch_postings(limit=10)}

    assert "Senior Platform Engineer" not in titles
    assert "Staff Data Engineer" not in titles
    assert "Founders Associate / Marketing & Growth" not in titles


def test_arbeitnow_adapter_includes_junior_and_intern_roles() -> None:
    adapter = ArbeitnowAdapter(fetch_json=_fake_arbeitnow_fetch_json)

    titles = {posting.payload.title for posting in adapter.fetch_postings(limit=10)}

    assert "Junior Python Developer" in titles
    assert "Machine Learning Intern" in titles
    assert "Working Student Data Analyst" in titles


def test_arbeitnow_sync_creates_policy_raw_postings_and_dedupes(db_session) -> None:
    first = sync_source_adapter(
        session=db_session,
        source_name="arbeitnow",
        limit=10,
        fetch_json=_fake_arbeitnow_fetch_json,
    )
    second = sync_source_adapter(
        session=db_session,
        source_name="arbeitnow",
        limit=10,
        fetch_json=_fake_arbeitnow_fetch_json,
    )

    assert first.ingestion_run.items_seen == 3
    assert first.ingestion_run.items_created == 3
    assert second.ingestion_run.items_created == 0
    assert second.duplicate_count == 3

    source = db_session.scalar(select(InternshipSource).where(InternshipSource.name == "Arbeitnow"))
    assert source is not None
    assert source.source_type == SourceType.API
    assert source.base_url == "https://www.arbeitnow.com/api/job-board-api"

    policy = db_session.scalar(select(SourcePolicy).where(SourcePolicy.source_id == source.id))
    assert policy is not None
    assert policy.policy_status == "allowed"
    assert policy.robots_checked_at is not None
    assert "Manual CLI sync" in policy.rate_limit_notes

    internships = list(db_session.scalars(select(Internship).where(Internship.source_id == source.id)))
    assert {internship.title for internship in internships} == {
        "Junior Python Developer",
        "Machine Learning Intern",
        "Working Student Data Analyst",
    }
    assert len(list(db_session.scalars(select(RawPosting).where(RawPosting.source_id == source.id)))) == 6
