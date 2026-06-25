from io import BytesIO

from sqlalchemy import select

from careeros.db.models.matching import SkillGapItem


def _create_profile_with_approved_claim(client, auth_headers) -> str:
    profile_response = client.post(
        "/profiles",
        headers=auth_headers,
        json={
            "display_name": "Gap Test Student",
            "email": "gap-test@example.com",
            "timezone": "Asia/Kolkata",
            "target_roles": ["ML Intern", "Backend Intern"],
            "target_locations": ["Remote"],
            "work_preferences": {},
        },
    )
    profile_id = profile_response.json()["id"]
    resume_text = """PROJECTS
CareerOS Backend
- Built FastAPI PostgreSQL Docker backend services with Python for internship discovery
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
        item for item in candidates_response.json()["items"]
        if item["candidate_kind"] == "claim"
    )
    client.post(
        f"/fact-candidates/{claim_candidate['id']}/approve",
        headers=auth_headers,
        json={"notes": "Verified for gap analysis tests."},
    )
    return profile_id


def _create_source(client, auth_headers) -> str:
    response = client.post(
        "/sources",
        headers=auth_headers,
        json={
            "name": "Gap Analysis Test Source",
            "source_type": "manual",
            "base_url": "https://gap.example.com",
            "is_active": True,
            "policy_status": "allowed",
        },
    )
    return response.json()["id"]


def _create_internship(
    client,
    auth_headers,
    source_id: str,
    *,
    external_id: str,
    title: str,
    description: str,
) -> str:
    response = client.post(
        f"/sources/{source_id}/ingest",
        headers=auth_headers,
        json={
            "postings": [
                {
                    "external_id": external_id,
                    "source_url": f"https://gap.example.com/jobs/{external_id}",
                    "title": title,
                    "company_name": "Gap Labs",
                    "company_domain": "gap.example.com",
                    "description": description,
                    "requirements": f"Requirements: {description}",
                    "responsibilities": "Build and evaluate production internship work.",
                    "application_url": f"https://gap.example.com/jobs/{external_id}/apply",
                    "location": "Worldwide Remote",
                    "work_mode": "Remote",
                }
            ]
        },
    )
    internship_id = response.json()["created_internships"][0]["id"]
    client.post(f"/internships/{internship_id}/normalize", headers=auth_headers)
    return internship_id


def _setup_gap_fixture(client, auth_headers) -> tuple[str, list[dict[str, object]]]:
    profile_id = _create_profile_with_approved_claim(client, auth_headers)
    source_id = _create_source(client, auth_headers)
    _create_internship(
        client,
        auth_headers,
        source_id,
        external_id="gap-ml-001",
        title="Machine Learning Intern",
        description=(
            "Python, Docker, Machine Learning, PyTorch, TensorFlow, and Deep Learning "
            "experience required."
        ),
    )
    _create_internship(
        client,
        auth_headers,
        source_id,
        external_id="gap-backend-001",
        title="Backend Intern",
        description="Python, FastAPI, PostgreSQL, Docker, SQL, and React experience required.",
    )
    match_response = client.post(
        "/matches/recompute",
        headers=auth_headers,
        json={"profile_id": profile_id},
    )
    return profile_id, match_response.json()["matches"]


def _match_by_title(matches: list[dict[str, object]], title: str) -> dict[str, object]:
    return next(
        match for match in matches
        if match["internship"]["title"] == title
    )


def test_match_gaps_detect_missing_and_covered_skills(client, auth_headers) -> None:
    _, matches = _setup_gap_fixture(client, auth_headers)
    match = _match_by_title(matches, "Machine Learning Intern")

    response = client.get(f"/matches/{match['id']}/gaps", headers=auth_headers)

    assert response.status_code == 200
    payload = response.json()
    missing_names = {item["skill"]["name"] for item in payload["missing_skills"]}
    covered_names = {item["skill_name"] for item in payload["covered_skills"]}
    assert {"PyTorch", "TensorFlow"} & missing_names
    assert {"Python", "Docker"} <= covered_names
    assert all(1 <= item["severity"] <= 5 for item in payload["missing_skills"])
    assert any(item["severity"] >= 4 for item in payload["missing_skills"])


def test_gap_analysis_prevents_duplicate_gap_records(client, auth_headers, db_session) -> None:
    _, matches = _setup_gap_fixture(client, auth_headers)
    match = _match_by_title(matches, "Machine Learning Intern")

    first_response = client.get(f"/matches/{match['id']}/gaps", headers=auth_headers)
    second_response = client.get(f"/matches/{match['id']}/gaps", headers=auth_headers)

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    gap_count = len(first_response.json()["missing_skills"])
    persisted = list(db_session.scalars(select(SkillGapItem)))
    assert len(persisted) == gap_count


def test_profile_skill_gaps_and_recommendations(client, auth_headers) -> None:
    profile_id, matches = _setup_gap_fixture(client, auth_headers)
    match = _match_by_title(matches, "Machine Learning Intern")
    client.get(f"/matches/{match['id']}/gaps", headers=auth_headers)

    gaps_response = client.get(
        f"/profiles/{profile_id}/skill-gaps",
        headers=auth_headers,
    )
    recommendations_response = client.get(
        f"/profiles/{profile_id}/recommendations",
        headers=auth_headers,
    )

    assert gaps_response.status_code == 200
    assert recommendations_response.status_code == 200
    gap_names = {item["skill"]["name"] for item in gaps_response.json()["items"]}
    recommendation_names = {
        item["skill_name"] for item in recommendations_response.json()["items"]
    }
    assert {"PyTorch", "TensorFlow", "React"} & gap_names
    assert {"PyTorch", "TensorFlow", "React"} & recommendation_names
    assert all(item["reason"] for item in recommendations_response.json()["items"])


def test_market_top_skill_aggregation(client, auth_headers) -> None:
    _setup_gap_fixture(client, auth_headers)

    overall_response = client.get("/market/top-skills", headers=auth_headers)
    ml_response = client.get("/market/top-skills/ml", headers=auth_headers)

    assert overall_response.status_code == 200
    assert ml_response.status_code == 200
    overall = overall_response.json()
    ml = ml_response.json()
    overall_names = {item["skill_name"] for item in overall["items"]}
    ml_names = {item["skill_name"] for item in ml["items"]}
    assert overall["total_internships"] == 2
    assert "Python" in overall_names
    assert {"PyTorch", "TensorFlow"} <= ml_names
    assert all(float(item["percentage"]) > 0 for item in overall["items"])
