from __future__ import annotations

from io import BytesIO
from uuid import UUID

from sqlalchemy import select

from careeros.db.models.embedding import EntityEmbedding
from careeros.db.models.internship import Internship, RawPosting
from careeros.db.models.matching import SkillGapItem
from careeros.services.job_discovery_service import run_job_discovery


def _remotive_discovery_payload() -> dict[str, object]:
    return {
        "jobs": [
            {
                "id": 201,
                "url": "https://remotive.com/remote-jobs/software-dev/ml-intern-201",
                "title": "Machine Learning Intern",
                "company_name": "Remote AI Lab",
                "candidate_required_location": "Worldwide",
                "description": (
                    "<p>Internship using Python, Machine Learning, PyTorch, "
                    "Pandas, NumPy, and SQL.</p>"
                ),
                "tags": ["python", "pytorch", "pandas", "numpy", "sql"],
                "category": "Software Development",
                "publication_date": "2026-06-20T12:00:00Z",
            },
            {
                "id": 202,
                "url": "https://remotive.com/remote-jobs/software-dev/backend-intern-202",
                "title": "Backend Intern",
                "company_name": "Remote Systems",
                "candidate_required_location": "Worldwide",
                "description": (
                    "<p>Internship building Python, FastAPI, PostgreSQL, "
                    "Docker, Git, and SQL APIs.</p>"
                ),
                "tags": ["python", "fastapi", "postgresql", "docker", "git", "sql"],
                "category": "Software Development",
                "publication_date": "2026-06-21T12:00:00Z",
            },
            {
                "id": 203,
                "url": "https://remotive.com/remote-jobs/software-dev/frontend-intern-203",
                "title": "Frontend Intern",
                "company_name": "Remote UI Co",
                "candidate_required_location": "Worldwide",
                "description": "<p>Internship building React, JavaScript, and CSS UI.</p>",
                "tags": ["react", "javascript", "css"],
                "category": "Software Development",
                "publication_date": "2026-06-22T12:00:00Z",
            },
        ]
    }


def _fake_fetch_json(url: str, headers: dict[str, str], timeout_seconds: int) -> dict[str, object]:
    assert "remotive.com" in url
    assert "CareerOS" in headers["User-Agent"]
    assert timeout_seconds == 30
    return _remotive_discovery_payload()


def _single_remotive_payload(job_id: int, title: str, company_name: str) -> dict[str, object]:
    slug = title.casefold().replace(" ", "-")
    return {
        "jobs": [
            {
                "id": job_id,
                "url": f"https://remotive.com/remote-jobs/software-dev/{slug}-{job_id}",
                "title": title,
                "company_name": company_name,
                "candidate_required_location": "Worldwide",
                "description": (
                    "<p>Entry-level role using Python, FastAPI, PostgreSQL, Docker, "
                    "Git, SQL, and REST APIs.</p>"
                ),
                "tags": ["python", "fastapi", "postgresql", "docker", "git", "sql"],
                "category": "Software Development",
                "publication_date": "2026-06-23T12:00:00Z",
            }
        ]
    }


def _fake_stale_fetch_json(
    url: str,
    headers: dict[str, str],
    timeout_seconds: int,
) -> dict[str, object]:
    return _single_remotive_payload(301, "Junior Backend Engineer", "Stale Remote Co")


def _fake_latest_fetch_json(
    url: str,
    headers: dict[str, str],
    timeout_seconds: int,
) -> dict[str, object]:
    return _single_remotive_payload(302, "Junior Data Engineer", "Latest Remote Co")


def _fake_arbeitnow_fetch_json(
    url: str,
    headers: dict[str, str],
    timeout_seconds: int,
) -> dict[str, object]:
    assert "arbeitnow.com" in url
    return {
        "data": [
            {
                "slug": "junior-backend-python",
                "title": "Junior Backend Python Developer",
                "company_name": "Arbeitnow Systems",
                "location": "Remote",
                "remote": True,
                "url": "https://www.arbeitnow.com/jobs/junior-backend-python",
                "description": (
                    "<p>Entry-level backend role using Python, FastAPI, PostgreSQL, "
                    "Docker, Git, SQL, and REST APIs.</p>"
                ),
                "tags": ["python", "fastapi", "postgresql", "docker", "git", "sql"],
                "job_types": ["full-time"],
                "created_at": 1782240000,
            },
            {
                "slug": "senior-backend-python",
                "title": "Senior Backend Python Developer",
                "company_name": "Arbeitnow Senior",
                "location": "Remote",
                "remote": True,
                "url": "https://www.arbeitnow.com/jobs/senior-backend-python",
                "description": "<p>Requires 8+ years of backend platform experience.</p>",
                "tags": ["python"],
                "job_types": ["full-time"],
                "created_at": 1782243600,
            },
        ]
    }


def _create_profile_with_approved_claims(client, auth_headers) -> str:
    profile_response = client.post(
        "/profiles",
        headers=auth_headers,
        json={
            "display_name": "Discovery Test Student",
            "email": "discovery-test@example.com",
            "timezone": "Asia/Kolkata",
            "target_roles": ["Machine Learning Intern", "Backend Intern"],
            "target_locations": ["Remote"],
            "work_preferences": {},
        },
    )
    profile_id = profile_response.json()["id"]
    resume_text = """PROJECTS
CareerOS Backend
- Built Python FastAPI PostgreSQL Docker backend services with SQL and Git.
ML Project
- Built Machine Learning models with Python, Pandas, NumPy, and SQL.
"""
    upload_response = client.post(
        "/documents/upload",
        headers=auth_headers,
        data={"profile_id": profile_id, "document_type": "resume"},
        files={"file": ("resume.txt", BytesIO(resume_text.encode("utf-8")), "text/plain")},
    )
    document_id = upload_response.json()["id"]
    client.post(f"/documents/{document_id}/extract", headers=auth_headers)
    candidates_response = client.get(
        f"/profiles/{profile_id}/fact-candidates",
        headers=auth_headers,
    )
    for candidate in candidates_response.json()["items"]:
        if candidate["candidate_kind"] in {"claim", "skill", "project"}:
            client.post(
                f"/fact-candidates/{candidate['id']}/approve",
                headers=auth_headers,
                json={"notes": "Approved for discovery pipeline tests."},
            )
    return profile_id


def test_job_discovery_pipeline_syncs_normalizes_matches_and_generates_gaps(
    client,
    auth_headers,
    db_session,
    app,
    app_settings,
) -> None:
    profile_id = _create_profile_with_approved_claims(client, auth_headers)

    outcome = run_job_discovery(
        session=db_session,
        profile_id=UUID(profile_id),
        source_name="remotive",
        limit=25,
        min_score=None,
        remote_only=False,
        role_family=None,
        provider=app.state.embedding_provider,
        settings=app_settings,
        top_matches=5,
        scope="latest-run",
        fetch_json=_fake_fetch_json,
    )

    assert outcome.items_seen == 3
    assert outcome.items_created == 3
    assert outcome.normalized_count == 3
    assert outcome.results
    assert all(result.match.total_score >= 0 for result in outcome.results)
    assert any(result.matched_skills for result in outcome.results)
    assert any(result.missing_skills for result in outcome.results)
    assert len(list(db_session.scalars(select(RawPosting)))) == 3
    assert len(list(db_session.scalars(select(Internship)))) == 3


def test_job_discovery_pipeline_is_idempotent_for_duplicates_embeddings_and_gaps(
    client,
    auth_headers,
    db_session,
    app,
    app_settings,
) -> None:
    profile_id = _create_profile_with_approved_claims(client, auth_headers)
    common_kwargs = {
        "session": db_session,
        "profile_id": UUID(profile_id),
        "source_name": "remotive",
        "limit": 25,
        "min_score": None,
        "remote_only": False,
        "role_family": None,
        "provider": app.state.embedding_provider,
        "settings": app_settings,
        "top_matches": 5,
        "scope": "latest-run",
        "fetch_json": _fake_fetch_json,
    }

    first = run_job_discovery(**common_kwargs)
    second = run_job_discovery(**common_kwargs)

    assert first.items_created == 3
    assert second.items_created == 0
    assert second.duplicate_count == 3
    assert len(list(db_session.scalars(select(Internship)))) == 3
    assert len(list(db_session.scalars(select(RawPosting)))) == 6

    active_embeddings = list(
        db_session.scalars(
            select(EntityEmbedding).where(EntityEmbedding.is_active.is_(True))
        )
    )
    entity_keys = {
        (embedding.entity_type, embedding.entity_id, embedding.embedding_version)
        for embedding in active_embeddings
    }
    assert len(active_embeddings) == len(entity_keys)

    for result in second.results:
        gap_keys = {
            (gap.skill_id, gap.skill_name_raw)
            for gap in db_session.scalars(
                select(SkillGapItem).where(
                    SkillGapItem.internship_match_id == result.match.id
                )
            )
        }
        assert len(gap_keys) == len(result.missing_skills)


def test_job_discovery_pipeline_filters_results(
    client,
    auth_headers,
    db_session,
    app,
    app_settings,
) -> None:
    profile_id = _create_profile_with_approved_claims(client, auth_headers)

    outcome = run_job_discovery(
        session=db_session,
        profile_id=UUID(profile_id),
        source_name="remotive",
        limit=25,
        min_score=None,
        remote_only=True,
        role_family="swe",
        provider=app.state.embedding_provider,
        settings=app_settings,
        top_matches=10,
        scope="source",
        fetch_json=_fake_fetch_json,
    )

    assert outcome.results
    assert all(result.internship.work_mode.value == "remote" for result in outcome.results)
    assert all(
        result.internship.normalized_title_ref is not None
        and result.internship.normalized_title_ref.role_family == "swe"
        for result in outcome.results
    )

    high_score = run_job_discovery(
        session=db_session,
        profile_id=UUID(profile_id),
        source_name="remotive",
        limit=25,
        min_score=outcome.results[0].match.total_score + 1,
        remote_only=True,
        role_family="swe",
        provider=app.state.embedding_provider,
        settings=app_settings,
        top_matches=10,
        scope="source",
        fetch_json=_fake_fetch_json,
    )
    assert not high_score.results


def test_job_discovery_source_scope_excludes_other_source_internships(
    client,
    auth_headers,
    db_session,
    app,
    app_settings,
) -> None:
    profile_id = _create_profile_with_approved_claims(client, auth_headers)
    source_response = client.post(
        "/sources",
        headers=auth_headers,
        json={
            "name": "Manual Pollution Source",
            "source_type": "manual",
            "base_url": "https://example.test/manual-pollution",
            "is_active": True,
            "policy_status": "allowed",
        },
    )
    source_id = source_response.json()["id"]
    client.post(
        f"/sources/{source_id}/ingest",
        headers=auth_headers,
        json={
            "postings": [
                {
                    "external_id": "manual-pollution-1",
                    "source_url": "https://example.test/manual-pollution/ml",
                    "title": "Machine Learning Intern",
                    "company_name": "Manual Pollution Co",
                    "description": "Python Machine Learning PyTorch Pandas NumPy SQL role.",
                    "requirements": "Python, PyTorch, Pandas, NumPy, SQL",
                    "application_url": "https://example.test/manual-pollution/apply",
                    "location": "Remote",
                    "work_mode": "Remote",
                }
            ]
        },
    )

    outcome = run_job_discovery(
        session=db_session,
        profile_id=UUID(profile_id),
        source_name="remotive",
        limit=25,
        min_score=None,
        remote_only=False,
        role_family=None,
        provider=app.state.embedding_provider,
        settings=app_settings,
        top_matches=10,
        scope="source",
        fetch_json=_fake_fetch_json,
    )

    assert outcome.results
    assert not outcome.polluted_by_other_sources
    assert all(result.internship.company_name != "Manual Pollution Co" for result in outcome.results)


def test_job_discovery_latest_run_scope_excludes_stale_source_internships(
    client,
    auth_headers,
    db_session,
    app,
    app_settings,
) -> None:
    profile_id = _create_profile_with_approved_claims(client, auth_headers)
    common_kwargs = {
        "session": db_session,
        "profile_id": UUID(profile_id),
        "source_name": "remotive",
        "limit": 25,
        "min_score": None,
        "remote_only": False,
        "role_family": None,
        "provider": app.state.embedding_provider,
        "settings": app_settings,
        "top_matches": 10,
        "scope": "latest-run",
    }

    stale = run_job_discovery(**common_kwargs, fetch_json=_fake_stale_fetch_json)
    latest = run_job_discovery(**common_kwargs, fetch_json=_fake_latest_fetch_json)

    assert stale.results
    assert latest.results
    assert latest.internships_considered == 1
    assert {result.internship.company_name for result in latest.results} == {"Latest Remote Co"}


def test_job_discovery_supports_arbeitnow_source_latest_run_scope(
    client,
    auth_headers,
    db_session,
    app,
    app_settings,
) -> None:
    profile_id = _create_profile_with_approved_claims(client, auth_headers)

    outcome = run_job_discovery(
        session=db_session,
        profile_id=UUID(profile_id),
        source_name="arbeitnow",
        limit=25,
        min_score=None,
        remote_only=False,
        role_family=None,
        provider=app.state.embedding_provider,
        settings=app_settings,
        top_matches=5,
        scope="latest-run",
        fetch_json=_fake_arbeitnow_fetch_json,
    )

    assert outcome.source_name == "arbeitnow"
    assert outcome.items_seen == 1
    assert outcome.items_created == 1
    assert outcome.internships_considered == 1
    assert not outcome.polluted_by_other_sources
    assert {result.internship.company_name for result in outcome.results} == {"Arbeitnow Systems"}
