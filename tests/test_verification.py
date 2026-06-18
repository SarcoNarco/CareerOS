from io import BytesIO
from uuid import UUID

from sqlalchemy import select

from careeros.db.models.fact_staging import FactCandidate, VerificationStatus
from careeros.db.models.verification import ApprovedClaim, VerificationEvent


def _create_extracted_candidate(client, auth_headers) -> tuple[str, str]:
    profile_response = client.post(
        "/profiles",
        headers=auth_headers,
        json={
            "display_name": "Sarosh",
            "email": "sarosh@example.com",
            "timezone": "Asia/Kolkata",
            "target_roles": ["ML Intern"],
            "target_locations": ["India"],
            "work_preferences": {},
        },
    )
    profile_id = profile_response.json()["id"]

    resume_text = """PROJECTS
Resume Matcher
- Built a FastAPI service to rank internship opportunities
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
    claim_candidate = next(
        item for item in candidates_response.json()["items"] if item["candidate_kind"] == "claim"
    )
    return profile_id, claim_candidate["id"]


def test_approve_candidate_creates_claim_and_event(client, auth_headers, db_session) -> None:
    _, candidate_id = _create_extracted_candidate(client, auth_headers)

    response = client.post(
        f"/fact-candidates/{candidate_id}/approve",
        headers=auth_headers,
        json={"notes": "Verified against source text."},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["fact_candidate"]["status"] == "approved"
    assert payload["approved_claim"] is not None
    assert payload["verification_event"]["action"] == "approve"

    candidate = db_session.scalar(select(FactCandidate).where(FactCandidate.id == UUID(candidate_id)))
    assert candidate is not None
    assert candidate.status == VerificationStatus.APPROVED

    approved_claim = db_session.scalar(
        select(ApprovedClaim).where(ApprovedClaim.approved_from_candidate_id == UUID(candidate_id))
    )
    assert approved_claim is not None
    assert approved_claim.claim_text

    event = db_session.scalar(
        select(VerificationEvent).where(VerificationEvent.fact_candidate_id == UUID(candidate_id))
    )
    assert event is not None
    assert event.action == "approve"


def test_reject_candidate_creates_event_only(client, auth_headers, db_session) -> None:
    _, candidate_id = _create_extracted_candidate(client, auth_headers)

    response = client.post(
        f"/fact-candidates/{candidate_id}/reject",
        headers=auth_headers,
        json={"notes": "Not strong enough to promote."},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["fact_candidate"]["status"] == "rejected"
    assert payload["approved_claim"] is None
    assert payload["verification_event"]["action"] == "reject"

    candidate = db_session.scalar(select(FactCandidate).where(FactCandidate.id == UUID(candidate_id)))
    assert candidate is not None
    assert candidate.status == VerificationStatus.REJECTED

    approved_claim = db_session.scalar(
        select(ApprovedClaim).where(ApprovedClaim.approved_from_candidate_id == UUID(candidate_id))
    )
    assert approved_claim is None

    event = db_session.scalar(
        select(VerificationEvent).where(VerificationEvent.fact_candidate_id == UUID(candidate_id))
    )
    assert event is not None
    assert event.action == "reject"


def test_edit_and_approve_preserves_candidate_and_stores_edited_claim(client, auth_headers, db_session) -> None:
    _, candidate_id = _create_extracted_candidate(client, auth_headers)

    response = client.post(
        f"/fact-candidates/{candidate_id}/edit-and-approve",
        headers=auth_headers,
        json={
            "claim_text": "Built a FastAPI service for internship ranking with deterministic scoring.",
            "notes": "Edited for clarity while preserving meaning.",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["fact_candidate"]["status"] == "edited"
    assert payload["approved_claim"]["claim_text"] == "Built a FastAPI service for internship ranking with deterministic scoring."
    assert payload["verification_event"]["action"] == "edit_and_approve"

    candidate = db_session.scalar(select(FactCandidate).where(FactCandidate.id == UUID(candidate_id)))
    assert candidate is not None
    assert candidate.status == VerificationStatus.EDITED
    assert candidate.structured_data["claim_text"] == "Built a FastAPI service to rank internship opportunities"

    approved_claim = db_session.scalar(
        select(ApprovedClaim).where(ApprovedClaim.approved_from_candidate_id == UUID(candidate_id))
    )
    assert approved_claim is not None
    assert approved_claim.claim_text == "Built a FastAPI service for internship ranking with deterministic scoring."

    event = db_session.scalar(
        select(VerificationEvent).where(VerificationEvent.fact_candidate_id == UUID(candidate_id))
    )
    assert event is not None
    assert event.action == "edit_and_approve"


def test_duplicate_approval_is_blocked(client, auth_headers) -> None:
    _, candidate_id = _create_extracted_candidate(client, auth_headers)

    first_response = client.post(
        f"/fact-candidates/{candidate_id}/approve",
        headers=auth_headers,
        json={"notes": "Verified."},
    )
    assert first_response.status_code == 200

    second_response = client.post(
        f"/fact-candidates/{candidate_id}/approve",
        headers=auth_headers,
        json={"notes": "Trying again."},
    )
    assert second_response.status_code == 409
    assert second_response.json()["detail"] == "Fact candidate has already been reviewed."
