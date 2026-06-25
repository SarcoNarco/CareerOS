from uuid import UUID

from sqlalchemy import select

from careeros.db.models.internship import (
    Internship,
    InternshipSkillRequirement,
    SkillCatalog,
    WorkMode,
)
from careeros.services.location_normalizer import normalize_location_to_record
from careeros.services.skill_normalizer import normalize_skill
from careeros.services.title_normalizer import normalize_title_to_record


def _source_payload() -> dict[str, object]:
    return {
        "name": "Sprint 4 Manual Source",
        "source_type": "manual",
        "base_url": "https://example.com",
        "is_active": True,
        "policy_status": "allowed",
    }


def _posting_payload() -> dict[str, object]:
    return {
        "external_id": "backend-ml-intern-001",
        "source_url": "https://example.com/jobs/backend-ml-intern-001",
        "title": "ML Engineer Intern",
        "company_name": "Example Labs",
        "company_domain": "example.com",
        "description": (
            "Work on machine learning services with Python, FastAPI, Docker, "
            "PostgreSQL, TypeScript, Node.js, AWS, and REST APIs."
        ),
        "requirements": (
            "Qualifications: Python, postgres, SQL, and PyTorch experience required. "
            "Tech stack includes TypeScript, Node.js, AWS, and REST APIs."
        ),
        "responsibilities": "Build APIs, evaluate ML models, and collaborate with GitHub workflows.",
        "application_url": "https://example.com/jobs/backend-ml-intern-001/apply",
        "location": "Worldwide Remote",
        "work_mode": "Remote",
    }


def _create_internship(client, auth_headers) -> str:
    source_response = client.post("/sources", headers=auth_headers, json=_source_payload())
    source_id = source_response.json()["id"]
    ingest_response = client.post(
        f"/sources/{source_id}/ingest",
        headers=auth_headers,
        json={"postings": [_posting_payload()]},
    )
    return ingest_response.json()["created_internships"][0]["id"]


def test_skill_alias_normalization(client, auth_headers, db_session) -> None:
    client.get("/skills", headers=auth_headers)

    postgres = normalize_skill(session=db_session, raw_skill_name="postgres")
    python = normalize_skill(session=db_session, raw_skill_name="py")

    assert postgres is not None
    assert postgres.name == "PostgreSQL"
    assert python is not None
    assert python.name == "Python"


def test_title_normalization(client, auth_headers, db_session) -> None:
    client.get("/skills", headers=auth_headers)

    ml_title = normalize_title_to_record(session=db_session, raw_title="Machine Learning Intern")
    ai_title = normalize_title_to_record(session=db_session, raw_title="AI Intern")
    data_title = normalize_title_to_record(session=db_session, raw_title="Data Science Intern")
    swe_title = normalize_title_to_record(session=db_session, raw_title="Backend Intern")

    assert ml_title.canonical_title == "ML"
    assert ai_title.canonical_title == "ML"
    assert data_title.canonical_title == "Data"
    assert swe_title.canonical_title == "SWE"


def test_location_normalization(client, auth_headers, db_session) -> None:
    client.get("/skills", headers=auth_headers)

    remote = normalize_location_to_record(
        session=db_session,
        location_text="Worldwide Remote",
        work_mode_text=None,
    )
    hybrid = normalize_location_to_record(
        session=db_session,
        location_text="Bengaluru",
        work_mode_text="Hybrid",
    )
    onsite = normalize_location_to_record(
        session=db_session,
        location_text="Mumbai office",
        work_mode_text=None,
    )

    assert remote.canonical_label == "Remote"
    assert remote.work_mode == WorkMode.REMOTE
    assert hybrid.canonical_label == "Hybrid"
    assert onsite.canonical_label == "Onsite"


def test_internship_normalize_extracts_and_persists_skill_requirements(
    client,
    auth_headers,
    db_session,
) -> None:
    internship_id = _create_internship(client, auth_headers)

    response = client.post(f"/internships/{internship_id}/normalize", headers=auth_headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload["normalized_title"]["canonical_title"] == "ML"
    assert payload["normalized_location"]["canonical_label"] == "Remote"
    assert payload["internship"]["normalized_title"] == "ML"
    assert payload["internship"]["normalized_location"] == "Remote"

    extracted_names = {item["skill"]["name"] for item in payload["skill_requirements"]}
    assert {
        "Python",
        "PostgreSQL",
        "SQL",
        "PyTorch",
        "FastAPI",
        "Docker",
        "Git",
        "Machine Learning",
        "TypeScript",
        "Node.js",
        "AWS",
        "REST APIs",
    } <= extracted_names
    assert all(item["extraction_method"] == "rules" for item in payload["skill_requirements"])

    internship = db_session.scalar(select(Internship).where(Internship.id == UUID(internship_id)))
    assert internship is not None
    assert internship.normalized_title_id is not None
    assert internship.normalized_location_id is not None

    requirements = list(
        db_session.scalars(
            select(InternshipSkillRequirement).where(
                InternshipSkillRequirement.internship_id == UUID(internship_id)
            )
        )
    )
    assert requirements
    assert any(requirement.is_required for requirement in requirements)

    skill = db_session.scalar(select(SkillCatalog).where(SkillCatalog.name == "PostgreSQL"))
    assert skill is not None
    assert any(requirement.skill_id == skill.id for requirement in requirements)


def test_internship_skills_endpoint_returns_persisted_requirements(client, auth_headers) -> None:
    internship_id = _create_internship(client, auth_headers)
    client.post(f"/internships/{internship_id}/normalize", headers=auth_headers)

    response = client.get(f"/internships/{internship_id}/skills", headers=auth_headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload["internship_id"] == internship_id
    assert any(item["skill"]["name"] == "Python" for item in payload["items"])


def test_skills_endpoint_returns_initial_catalog(client, auth_headers) -> None:
    response = client.get("/skills", headers=auth_headers)

    assert response.status_code == 200
    names = {item["name"] for item in response.json()["items"]}
    assert {"Python", "PostgreSQL", "Machine Learning", "FastAPI", "TypeScript", "AWS"} <= names
