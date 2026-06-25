from io import BytesIO
from uuid import UUID

from sqlalchemy import select

from careeros.db.models.fact_staging import CandidateKind, ExtractionRun, ExtractionStatus, FactCandidate, FactEvidenceSpan


def test_extract_document_creates_staging_records(client, auth_headers, db_session) -> None:
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

    resume_text = """EDUCATION
Indian Institute of Technology, Computer Science, GPA 8.7

PROJECTS
Resume Matcher
- Built a FastAPI service to rank internship opportunities
- Improved matching accuracy by 12 percent using deterministic scoring

SKILLS
Python, FastAPI, PostgreSQL, Machine Learning
"""

    upload_response = client.post(
        "/documents/upload",
        headers=auth_headers,
        data={"profile_id": profile_id, "document_type": "resume"},
        files={"file": ("resume.txt", BytesIO(resume_text.encode("utf-8")), "text/plain")},
    )
    document_id = upload_response.json()["id"]
    assert upload_response.json()["extracted_text"] == resume_text

    extract_response = client.post(
        f"/documents/{document_id}/extract",
        headers=auth_headers,
    )

    assert extract_response.status_code == 200
    payload = extract_response.json()
    assert payload["status"] == "succeeded"
    assert payload["candidate_count"] >= 4
    assert payload["evidence_span_count"] >= payload["candidate_count"]
    assert payload["candidates_by_kind"]["education"] >= 1
    assert payload["candidates_by_kind"]["project"] >= 1
    assert payload["candidates_by_kind"]["skill"] >= 1
    assert payload["candidates_by_kind"]["claim"] >= 1

    extraction_run = db_session.scalar(
        select(ExtractionRun).where(ExtractionRun.id == UUID(payload["extraction_run_id"]))
    )
    assert extraction_run is not None
    assert extraction_run.status == ExtractionStatus.SUCCEEDED

    candidates = db_session.scalars(
        select(FactCandidate).where(FactCandidate.extraction_run_id == extraction_run.id)
    ).all()
    assert candidates
    assert any(candidate.candidate_kind == CandidateKind.EDUCATION for candidate in candidates)
    assert any(candidate.candidate_kind == CandidateKind.PROJECT for candidate in candidates)
    assert any(candidate.candidate_kind == CandidateKind.SKILL for candidate in candidates)
    assert any(candidate.candidate_kind == CandidateKind.CLAIM for candidate in candidates)

    evidence_spans = db_session.scalars(
        select(FactEvidenceSpan).join(FactCandidate).where(
            FactCandidate.extraction_run_id == extraction_run.id
        )
    ).all()
    assert evidence_spans
    assert all(span.snippet_text for span in evidence_spans)


def test_extract_document_generates_balanced_student_resume_candidates(
    client,
    auth_headers,
) -> None:
    profile_response = client.post(
        "/profiles",
        headers=auth_headers,
        json={
            "display_name": "Student",
            "email": "student@example.com",
            "timezone": "Asia/Kolkata",
            "target_roles": ["ML Intern", "Software Engineering Intern"],
            "target_locations": ["India", "Remote"],
            "work_preferences": {},
        },
    )
    profile_id = profile_response.json()["id"]

    resume_text = """EDUCATION
ABC Institute of Technology, B.Tech Computer Science, 2025

EXPERIENCE
Software Engineering Intern, Example Labs
- Developed REST APIs using FastAPI and PostgreSQL for an internal dashboard
- Automated deployment checks with Docker and GitHub Actions

PROJECTS
Resume Matcher
- Built a FastAPI service to rank internship opportunities using PostgreSQL
- Improved matching accuracy by 12 percent using deterministic scoring

Plant Disease Classifier
- Trained a CNN model in PyTorch to classify crop disease images
- Visualized model predictions with Python and Streamlit

SKILLS
Languages: Python, JavaScript, SQL, C++
Frameworks: FastAPI, React, PyTorch, TensorFlow
Tools: PostgreSQL, Docker, Git, GitHub Actions, Streamlit
"""

    upload_response = client.post(
        "/documents/upload",
        headers=auth_headers,
        data={"profile_id": profile_id, "document_type": "resume"},
        files={"file": ("resume.txt", BytesIO(resume_text.encode("utf-8")), "text/plain")},
    )
    document_id = upload_response.json()["id"]

    extract_response = client.post(
        f"/documents/{document_id}/extract",
        headers=auth_headers,
    )

    assert extract_response.status_code == 200
    payload = extract_response.json()
    counts = payload["candidates_by_kind"]
    assert counts["education"] >= 1
    assert counts["experience"] >= 1
    assert counts["project"] >= 2
    assert counts["claim"] >= 5
    assert 4 <= counts["skill"] <= 28

    candidates_response = client.get(
        f"/profiles/{profile_id}/fact-candidates",
        headers=auth_headers,
    )
    candidates = candidates_response.json()["items"]
    project_candidates = [
        candidate for candidate in candidates if candidate["candidate_kind"] == "project"
    ]
    experience_candidates = [
        candidate for candidate in candidates if candidate["candidate_kind"] == "experience"
    ]
    claim_candidates = [
        candidate for candidate in candidates if candidate["candidate_kind"] == "claim"
    ]
    assert {candidate["structured_data"]["name"] for candidate in project_candidates} == {
        "Resume Matcher",
        "Plant Disease Classifier",
    }
    assert experience_candidates[0]["structured_data"]["role_or_company"] == (
        "Software Engineering Intern, Example Labs"
    )
    assert any(
        candidate["structured_data"]["source_section"] == "projects"
        for candidate in claim_candidates
    )
    assert any(
        candidate["structured_data"]["source_section"] == "experience"
        for candidate in claim_candidates
    )

    diagnostics_response = client.get(
        f"/extraction-runs/{payload['extraction_run_id']}/diagnostics",
        headers=auth_headers,
    )

    assert diagnostics_response.status_code == 200
    diagnostics = diagnostics_response.json()
    assert diagnostics["sections_detected"].keys() >= {
        "education",
        "experience",
        "projects",
        "skills",
    }
    assert diagnostics["candidate_counts_by_type"]["project"] >= 2
    assert diagnostics["claim_counts_by_type"]["projects"] >= 4
    assert diagnostics["claim_counts_by_type"]["experience"] >= 2
    assert diagnostics["quality_metrics"]["project_candidate_count"] >= 2
    assert "No project candidates generated." not in diagnostics["warnings"]
