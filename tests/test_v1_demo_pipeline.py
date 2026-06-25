from io import BytesIO
import json
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
SAMPLE_RESUME = ROOT_DIR / "samples" / "demo_resume.txt"
SAMPLE_INTERNSHIPS = ROOT_DIR / "samples" / "demo_internships.json"


def test_v1_demo_pipeline_smoke(client, auth_headers) -> None:
    resume_text = SAMPLE_RESUME.read_text(encoding="utf-8")
    postings = json.loads(SAMPLE_INTERNSHIPS.read_text(encoding="utf-8"))

    profile_response = client.post(
        "/profiles",
        headers=auth_headers,
        json={
            "display_name": "CareerOS Demo Test Student",
            "email": "careeros.demo.test@example.test",
            "timezone": "Asia/Kolkata",
            "headline": "Computer Science student exploring AI, data, and software internships",
            "target_roles": ["Machine Learning Intern", "Data Science Intern", "Backend Intern"],
            "target_locations": ["Remote", "India"],
            "work_preferences": {"demo": True},
        },
    )
    assert profile_response.status_code == 201
    profile_id = profile_response.json()["id"]

    upload_response = client.post(
        "/documents/upload",
        headers=auth_headers,
        data={"profile_id": profile_id, "document_type": "resume"},
        files={"file": ("demo_resume.txt", BytesIO(resume_text.encode("utf-8")), "text/plain")},
    )
    assert upload_response.status_code == 201
    document_id = upload_response.json()["id"]

    extraction_response = client.post(f"/documents/{document_id}/extract", headers=auth_headers)
    assert extraction_response.status_code == 200
    extraction = extraction_response.json()
    assert extraction["candidate_count"] >= 10
    assert extraction["candidates_by_kind"]["claim"] >= 4

    candidates_response = client.get(
        f"/profiles/{profile_id}/fact-candidates",
        headers=auth_headers,
    )
    candidates = candidates_response.json()["items"]
    approvable = [
        candidate
        for candidate in candidates
        if candidate["status"] == "pending"
        and candidate["candidate_kind"] in {"education", "experience", "project", "skill", "claim"}
    ]
    assert approvable
    for candidate in approvable:
        response = client.post(
            f"/fact-candidates/{candidate['id']}/approve",
            headers=auth_headers,
            json={"notes": "Approved by V1 demo smoke test."},
        )
        assert response.status_code == 200

    source_response = client.post(
        "/sources",
        headers=auth_headers,
        json={
            "name": "CareerOS Demo Source Test",
            "source_type": "manual",
            "base_url": "https://demo.example.test",
            "is_active": True,
            "policy_status": "allowed",
        },
    )
    assert source_response.status_code == 201
    source_id = source_response.json()["id"]

    ingest_response = client.post(
        f"/sources/{source_id}/ingest",
        headers=auth_headers,
        json={"postings": postings},
    )
    assert ingest_response.status_code == 200
    internships = ingest_response.json()["created_internships"]
    assert len(internships) == 4

    for internship in internships:
        normalize_response = client.post(
            f"/internships/{internship['id']}/normalize",
            headers=auth_headers,
        )
        assert normalize_response.status_code == 200
        embed_response = client.post(
            f"/internships/{internship['id']}/embed",
            headers=auth_headers,
        )
        assert embed_response.status_code == 200

    profile_embed_response = client.post(f"/profiles/{profile_id}/embed", headers=auth_headers)
    assert profile_embed_response.status_code == 200
    assert profile_embed_response.json()["embeddings"]

    rebuild_response = client.post(
        "/embeddings/rebuild",
        headers=auth_headers,
        json={"process": True, "limit": 200},
    )
    assert rebuild_response.status_code == 200

    matches_response = client.post(
        "/matches/recompute",
        headers=auth_headers,
        json={"profile_id": profile_id},
    )
    assert matches_response.status_code == 200
    matches = matches_response.json()["matches"]
    assert len(matches) == 4
    top_match = matches[0]

    gaps_response = client.get(f"/matches/{top_match['id']}/gaps", headers=auth_headers)
    assert gaps_response.status_code == 200
    assert "missing_skills" in gaps_response.json()
    assert "covered_skills" in gaps_response.json()

    resume_response = client.post(
        "/resumes/generate",
        headers=auth_headers,
        json={
            "profile_id": profile_id,
            "internship_id": top_match["internship_id"],
            "max_claims": 10,
        },
    )
    assert resume_response.status_code == 201
    resume = resume_response.json()
    assert resume["resume"]["rendered_html_path"]
    assert resume["claims"]
    assert all(
        claim["rendered_text"] == claim["approved_claim"]["claim_text"]
        for claim in resume["claims"]
    )
