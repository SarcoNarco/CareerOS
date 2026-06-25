from io import BytesIO
from uuid import UUID

from sqlalchemy import select

from careeros.db.models.matching import InternshipMatch, MatchRun


def _create_profile_with_claim(client, auth_headers) -> str:
    profile_response = client.post(
        "/profiles",
        headers=auth_headers,
        json={
            "display_name": "Sarosh",
            "email": "sarosh-matching@example.com",
            "timezone": "Asia/Kolkata",
            "target_roles": ["Backend Intern", "ML Intern"],
            "target_locations": ["Remote"],
            "work_preferences": {},
        },
    )
    profile_id = profile_response.json()["id"]
    resume_text = """PROJECTS
CareerOS
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
        item for item in candidates_response.json()["items"] if item["candidate_kind"] == "claim"
    )
    client.post(
        f"/fact-candidates/{claim_candidate['id']}/approve",
        headers=auth_headers,
        json={"notes": "Verified for matching tests."},
    )
    return profile_id


def _create_source(client, auth_headers) -> str:
    response = client.post(
        "/sources",
        headers=auth_headers,
        json={
            "name": "Matching Test Source",
            "source_type": "manual",
            "base_url": "https://example.com",
            "is_active": True,
            "policy_status": "allowed",
        },
    )
    return response.json()["id"]


def _create_internship(
    client,
    auth_headers,
    source_id: str,
    external_id: str,
    title: str,
    description: str,
    location: str = "Worldwide Remote",
    work_mode: str = "Remote",
) -> str:
    response = client.post(
        f"/sources/{source_id}/ingest",
        headers=auth_headers,
        json={
            "postings": [
                {
                    "external_id": external_id,
                    "source_url": f"https://example.com/jobs/{external_id}",
                    "title": title,
                    "company_name": "Example Labs",
                    "company_domain": "example.com",
                    "description": description,
                    "requirements": description,
                    "responsibilities": "Collaborate with engineering teams.",
                    "application_url": f"https://example.com/jobs/{external_id}/apply",
                    "location": location,
                    "work_mode": work_mode,
                }
            ]
        },
    )
    internship_id = response.json()["created_internships"][0]["id"]
    client.post(f"/internships/{internship_id}/normalize", headers=auth_headers)
    return internship_id


def _setup_matching_fixture(client, auth_headers) -> tuple[str, str, str]:
    profile_id = _create_profile_with_claim(client, auth_headers)
    source_id = _create_source(client, auth_headers)
    backend_id = _create_internship(
        client,
        auth_headers,
        source_id,
        external_id="matching-backend-001",
        title="Backend Intern",
        description="Build FastAPI PostgreSQL Docker backend services with Python APIs.",
    )
    data_id = _create_internship(
        client,
        auth_headers,
        source_id,
        external_id="matching-data-001",
        title="Data Analyst Intern",
        description="Create dashboards using spreadsheets, reporting workflows, and business metrics.",
    )
    return profile_id, backend_id, data_id


def test_match_recompute_creates_run_and_matches(client, auth_headers, db_session) -> None:
    profile_id, _, _ = _setup_matching_fixture(client, auth_headers)

    response = client.post(
        "/matches/recompute",
        headers=auth_headers,
        json={"profile_id": profile_id},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["match_run"]["status"] == "succeeded"
    assert len(payload["matches"]) == 2

    match_run = db_session.scalar(
        select(MatchRun).where(MatchRun.id == UUID(payload["match_run"]["id"]))
    )
    assert match_run is not None

    matches = list(db_session.scalars(select(InternshipMatch)))
    assert len(matches) == 2
    assert all(match.match_run_id == match_run.id for match in matches)


def test_score_calculation_uses_v2_weights(client, auth_headers) -> None:
    profile_id, _, _ = _setup_matching_fixture(client, auth_headers)

    response = client.post(
        "/matches/recompute",
        headers=auth_headers,
        json={"profile_id": profile_id},
    )

    match = response.json()["matches"][0]
    expected_total = (
        0.40 * float(match["normalized_feature_score"])
        + 0.25 * float(match["semantic_score"])
        + 0.20 * float(match["skill_score"])
        + 0.15 * float(match["experience_score"])
        - float(match["gap_penalty"])
    )
    assert abs(float(match["total_score"]) - expected_total) < 0.02


def test_ranking_order_prefers_best_fit(client, auth_headers) -> None:
    profile_id, backend_id, data_id = _setup_matching_fixture(client, auth_headers)

    response = client.post(
        "/matches/recompute",
        headers=auth_headers,
        json={"profile_id": profile_id},
    )

    matches = response.json()["matches"]
    assert matches[0]["internship"]["id"] == backend_id
    assert matches[1]["internship"]["id"] == data_id
    assert float(matches[0]["total_score"]) > float(matches[1]["total_score"])


def test_explanation_payload_is_structured_and_deterministic(client, auth_headers) -> None:
    profile_id, _, _ = _setup_matching_fixture(client, auth_headers)

    response = client.post(
        "/matches/recompute",
        headers=auth_headers,
        json={"profile_id": profile_id},
    )

    explanation = response.json()["matches"][0]["explanation_json"]
    assert explanation["summary"]["llm_generated"] is False
    assert explanation["weights"]["normalized_feature_score"] == 0.4
    assert "matched_skills" in explanation["signals"]
    assert "fastapi" in explanation["signals"]["matched_skills"]


def test_top_matches_endpoint_returns_profile_matches(client, auth_headers) -> None:
    profile_id, backend_id, _ = _setup_matching_fixture(client, auth_headers)
    client.post(
        "/matches/recompute",
        headers=auth_headers,
        json={"profile_id": profile_id},
    )

    response = client.get(
        f"/profiles/{profile_id}/top-matches",
        headers=auth_headers,
        params={"limit": 1},
    )

    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["internship"]["id"] == backend_id


def test_get_match_endpoint_returns_single_match(client, auth_headers) -> None:
    profile_id, _, _ = _setup_matching_fixture(client, auth_headers)
    recompute_response = client.post(
        "/matches/recompute",
        headers=auth_headers,
        json={"profile_id": profile_id},
    )
    match_id = recompute_response.json()["matches"][0]["id"]

    response = client.get(f"/matches/{match_id}", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["id"] == match_id
