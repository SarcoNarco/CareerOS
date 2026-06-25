from io import BytesIO
from pathlib import Path
from uuid import UUID

from sqlalchemy import select

from careeros.db.base import utc_now
from careeros.db.models.profile import Profile
from careeros.db.models.resume import GeneratedResume, GeneratedResumeClaim
from careeros.db.models.source_document import SourceDocument
from careeros.db.models.verification import ApprovedClaim, ClaimStatus


def _create_profile_and_document(client, auth_headers) -> tuple[str, str]:
    profile_response = client.post(
        "/profiles",
        headers=auth_headers,
        json={
            "display_name": "Resume Test Student",
            "email": "resume-test@example.com",
            "timezone": "Asia/Kolkata",
            "headline": "Computer Science student",
            "target_roles": ["ML Intern", "Backend Intern"],
            "target_locations": ["Remote"],
            "work_preferences": {},
        },
    )
    profile_id = profile_response.json()["id"]
    upload_response = client.post(
        "/documents/upload",
        headers=auth_headers,
        data={"profile_id": profile_id, "document_type": "resume"},
        files={
            "file": (
                "resume.txt",
                BytesIO(b"Verified source document for resume generation tests."),
                "text/plain",
            )
        },
    )
    return profile_id, upload_response.json()["id"]


def _create_internship(
    client,
    auth_headers,
    *,
    title: str,
    description: str,
    external_id: str,
) -> str:
    source_response = client.post(
        "/sources",
        headers=auth_headers,
        json={
            "name": f"Resume Source {external_id}",
            "source_type": "manual",
            "base_url": "https://resume.example.com",
            "is_active": True,
            "policy_status": "allowed",
        },
    )
    source_id = source_response.json()["id"]
    ingest_response = client.post(
        f"/sources/{source_id}/ingest",
        headers=auth_headers,
        json={
            "postings": [
                {
                    "external_id": external_id,
                    "source_url": f"https://resume.example.com/jobs/{external_id}",
                    "title": title,
                    "company_name": "Resume Labs",
                    "description": description,
                    "requirements": f"Requirements: {description}",
                    "responsibilities": "Build verified project work.",
                    "application_url": f"https://resume.example.com/jobs/{external_id}/apply",
                    "location": "Worldwide Remote",
                    "work_mode": "Remote",
                }
            ]
        },
    )
    internship_id = ingest_response.json()["created_internships"][0]["id"]
    client.post(f"/internships/{internship_id}/normalize", headers=auth_headers)
    return internship_id


def _insert_claims(db_session, profile_id: str, document_id: str) -> dict[str, str]:
    profile = db_session.scalar(select(Profile).where(Profile.id == UUID(profile_id)))
    document = db_session.scalar(
        select(SourceDocument).where(SourceDocument.id == UUID(document_id))
    )
    assert profile is not None
    assert document is not None

    timestamp = utc_now()
    claims = {
        "backend": ApprovedClaim(
            profile_id=profile.id,
            owning_entity_type="project",
            owning_entity_id=None,
            claim_text="Built FastAPI PostgreSQL APIs with Python.",
            claim_type="claim",
            status=ClaimStatus.APPROVED,
            source_document_id=document.id,
            source_primary_span_id=None,
            approved_from_candidate_id=None,
            approved_at=timestamp,
            retired_at=None,
        ),
        "ml": ApprovedClaim(
            profile_id=profile.id,
            owning_entity_type="project",
            owning_entity_id=None,
            claim_text="Trained PyTorch computer vision model for image classification.",
            claim_type="claim",
            status=ClaimStatus.APPROVED,
            source_document_id=document.id,
            source_primary_span_id=None,
            approved_from_candidate_id=None,
            approved_at=timestamp,
            retired_at=None,
        ),
        "education": ApprovedClaim(
            profile_id=profile.id,
            owning_entity_type="education",
            owning_entity_id=None,
            claim_text="Studying Computer Science with coursework in machine learning.",
            claim_type="summary",
            status=ClaimStatus.APPROVED,
            source_document_id=document.id,
            source_primary_span_id=None,
            approved_from_candidate_id=None,
            approved_at=timestamp,
            retired_at=None,
        ),
        "rejected": ApprovedClaim(
            profile_id=profile.id,
            owning_entity_type="project",
            owning_entity_id=None,
            claim_text="Rejected claim must never appear.",
            claim_type="claim",
            status=ClaimStatus.REJECTED,
            source_document_id=document.id,
            source_primary_span_id=None,
            approved_from_candidate_id=None,
            approved_at=timestamp,
            retired_at=None,
        ),
        "pending": ApprovedClaim(
            profile_id=profile.id,
            owning_entity_type="project",
            owning_entity_id=None,
            claim_text="Pending claim must never appear.",
            claim_type="claim",
            status=ClaimStatus.PENDING,
            source_document_id=document.id,
            source_primary_span_id=None,
            approved_from_candidate_id=None,
            approved_at=timestamp,
            retired_at=None,
        ),
        "retired": ApprovedClaim(
            profile_id=profile.id,
            owning_entity_type="skill",
            owning_entity_id=None,
            claim_text="Retired claim must never appear.",
            claim_type="skill",
            status=ClaimStatus.APPROVED,
            source_document_id=document.id,
            source_primary_span_id=None,
            approved_from_candidate_id=None,
            approved_at=timestamp,
            retired_at=timestamp,
        ),
    }
    db_session.add_all(claims.values())
    db_session.commit()
    return {key: value.claim_text for key, value in claims.items()}


def test_generate_resume_uses_approved_claims_only_and_traces_them(
    client,
    auth_headers,
    db_session,
) -> None:
    profile_id, document_id = _create_profile_and_document(client, auth_headers)
    internship_id = _create_internship(
        client,
        auth_headers,
        title="Machine Learning Intern",
        description="Python, PyTorch, computer vision, and machine learning experience required.",
        external_id="resume-ml-001",
    )
    claim_texts = _insert_claims(db_session, profile_id, document_id)

    response = client.post(
        "/resumes/generate",
        headers=auth_headers,
        json={"profile_id": profile_id, "internship_id": internship_id, "max_claims": 3},
    )

    assert response.status_code == 201
    payload = response.json()
    resume = payload["resume"]
    rendered_claims = payload["claims"]
    rendered_texts = {claim["rendered_text"] for claim in rendered_claims}
    allowed_texts = {claim_texts["backend"], claim_texts["ml"], claim_texts["education"]}
    blocked_texts = {claim_texts["rejected"], claim_texts["pending"], claim_texts["retired"]}

    assert rendered_texts <= allowed_texts
    assert claim_texts["ml"] in rendered_texts
    assert not rendered_texts & blocked_texts
    assert len(rendered_claims) == len(rendered_texts)

    persisted_resume = db_session.scalar(
        select(GeneratedResume).where(GeneratedResume.id == UUID(resume["id"]))
    )
    assert persisted_resume is not None
    assert persisted_resume.rendered_html_path is not None
    html = Path(persisted_resume.rendered_html_path).read_text(encoding="utf-8")
    assert claim_texts["ml"] in html
    assert "Rejected claim must never appear." not in html
    assert "Pending claim must never appear." not in html
    assert "Retired claim must never appear." not in html

    trace_rows = list(
        db_session.scalars(
            select(GeneratedResumeClaim).where(
                GeneratedResumeClaim.generated_resume_id == persisted_resume.id
            )
        )
    )
    assert len(trace_rows) == len(rendered_claims)
    assert {row.rendered_text for row in trace_rows} == rendered_texts


def test_target_internship_influences_claim_selection(client, auth_headers, db_session) -> None:
    profile_id, document_id = _create_profile_and_document(client, auth_headers)
    ml_internship_id = _create_internship(
        client,
        auth_headers,
        title="Machine Learning Intern",
        description="PyTorch computer vision and machine learning required.",
        external_id="resume-ml-002",
    )
    backend_internship_id = _create_internship(
        client,
        auth_headers,
        title="Backend Intern",
        description="FastAPI PostgreSQL Python APIs required.",
        external_id="resume-backend-002",
    )
    claim_texts = _insert_claims(db_session, profile_id, document_id)

    ml_response = client.post(
        "/resumes/generate",
        headers=auth_headers,
        json={"profile_id": profile_id, "internship_id": ml_internship_id, "max_claims": 1},
    )
    backend_response = client.post(
        "/resumes/generate",
        headers=auth_headers,
        json={"profile_id": profile_id, "internship_id": backend_internship_id, "max_claims": 1},
    )

    assert ml_response.status_code == 201
    assert backend_response.status_code == 201
    assert ml_response.json()["claims"][0]["rendered_text"] == claim_texts["ml"]
    assert backend_response.json()["claims"][0]["rendered_text"] == claim_texts["backend"]


def test_resume_detail_and_claim_endpoints_return_traceability(
    client,
    auth_headers,
    db_session,
) -> None:
    profile_id, document_id = _create_profile_and_document(client, auth_headers)
    _insert_claims(db_session, profile_id, document_id)

    generate_response = client.post(
        "/resumes/generate",
        headers=auth_headers,
        json={"profile_id": profile_id, "max_claims": 2},
    )
    resume_id = generate_response.json()["resume"]["id"]

    detail_response = client.get(f"/resumes/{resume_id}", headers=auth_headers)
    claims_response = client.get(f"/resumes/{resume_id}/claims", headers=auth_headers)
    list_response = client.get(f"/profiles/{profile_id}/resumes", headers=auth_headers)
    html_response = client.get(f"/resumes/{resume_id}/html", headers=auth_headers)

    assert detail_response.status_code == 200
    assert claims_response.status_code == 200
    assert list_response.status_code == 200
    assert html_response.status_code == 200
    detail_claims = detail_response.json()["claims"]
    claim_items = claims_response.json()["items"]
    assert claims_response.json()["resume_id"] == resume_id
    assert list_response.json()["items"][0]["id"] == resume_id
    assert "Resume Test Student" in html_response.text
    assert [item["rendered_text"] for item in claim_items] == [
        item["rendered_text"] for item in detail_claims
    ]
    assert all(item["approved_claim"] is not None for item in claim_items)
