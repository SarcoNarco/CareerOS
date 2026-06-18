from uuid import UUID

from sqlalchemy import select

from careeros.db.models.internship import IngestionRun, Internship, InternshipSource, RawPosting


def _source_payload() -> dict[str, object]:
    return {
        "name": "Manual Test Source",
        "source_type": "manual",
        "base_url": "https://example.com",
        "is_active": True,
        "policy_status": "allowed",
        "policy_notes": "Manual test payloads only.",
    }


def _posting_payload() -> dict[str, object]:
    return {
        "external_id": "ml-intern-001",
        "source_url": "https://example.com/jobs/ml-intern-001",
        "title": "Machine Learning Internship",
        "company_name": "Example AI",
        "company_domain": "example.com",
        "description": "Build and evaluate ML models for internship discovery.",
        "requirements": "Python, SQL, machine learning basics.",
        "responsibilities": "Prototype data pipelines and model evaluation scripts.",
        "application_url": "https://example.com/jobs/ml-intern-001/apply",
        "location": "Worldwide Remote",
        "work_mode": "Remote",
        "metadata": {"source_note": "seeded manually"},
    }


def test_source_creation(client, auth_headers, db_session) -> None:
    response = client.post("/sources", headers=auth_headers, json=_source_payload())

    assert response.status_code == 201
    payload = response.json()
    assert payload["name"] == "Manual Test Source"
    assert payload["source_type"] == "manual"
    assert payload["policy"]["policy_status"] == "allowed"

    source = db_session.scalar(select(InternshipSource).where(InternshipSource.id == UUID(payload["id"])))
    assert source is not None
    assert source.name == "Manual Test Source"


def test_manual_ingestion_creates_run_raw_posting_and_internship(client, auth_headers, db_session) -> None:
    source_response = client.post("/sources", headers=auth_headers, json=_source_payload())
    source_id = source_response.json()["id"]

    response = client.post(
        f"/sources/{source_id}/ingest",
        headers=auth_headers,
        json={"postings": [_posting_payload()]},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ingestion_run"]["items_seen"] == 1
    assert payload["ingestion_run"]["items_created"] == 1
    assert payload["duplicate_count"] == 0
    assert len(payload["created_internships"]) == 1
    assert payload["created_internships"][0]["normalized_title"] == "machine learning intern"
    assert payload["created_internships"][0]["normalized_location"] == "remote"
    assert payload["created_internships"][0]["work_mode"] == "remote"

    ingestion_run = db_session.scalar(
        select(IngestionRun).where(IngestionRun.id == UUID(payload["ingestion_run"]["id"]))
    )
    assert ingestion_run is not None
    assert ingestion_run.items_created == 1

    raw_posting = db_session.scalar(select(RawPosting).where(RawPosting.ingestion_run_id == ingestion_run.id))
    assert raw_posting is not None
    assert raw_posting.payload_json["title"] == "Machine Learning Internship"

    internship = db_session.scalar(select(Internship).where(Internship.raw_posting_id == raw_posting.id))
    assert internship is not None
    assert internship.company_name == "Example AI"


def test_duplicate_ingestion_prevents_duplicate_internship(client, auth_headers, db_session) -> None:
    source_response = client.post("/sources", headers=auth_headers, json=_source_payload())
    source_id = source_response.json()["id"]
    request_payload = {"postings": [_posting_payload()]}

    first_response = client.post(
        f"/sources/{source_id}/ingest",
        headers=auth_headers,
        json=request_payload,
    )
    assert first_response.status_code == 200
    assert first_response.json()["ingestion_run"]["items_created"] == 1

    second_response = client.post(
        f"/sources/{source_id}/ingest",
        headers=auth_headers,
        json=request_payload,
    )
    assert second_response.status_code == 200
    assert second_response.json()["ingestion_run"]["items_created"] == 0
    assert second_response.json()["duplicate_count"] == 1

    internships = list(db_session.scalars(select(Internship)))
    raw_postings = list(db_session.scalars(select(RawPosting)))
    ingestion_runs = list(db_session.scalars(select(IngestionRun)))
    assert len(internships) == 1
    assert len(raw_postings) == 2
    assert len(ingestion_runs) == 2


def test_internships_can_be_queried(client, auth_headers) -> None:
    source_response = client.post("/sources", headers=auth_headers, json=_source_payload())
    source_id = source_response.json()["id"]
    ingest_response = client.post(
        f"/sources/{source_id}/ingest",
        headers=auth_headers,
        json={"postings": [_posting_payload()]},
    )
    internship_id = ingest_response.json()["created_internships"][0]["id"]

    list_response = client.get("/internships", headers=auth_headers)
    assert list_response.status_code == 200
    assert len(list_response.json()["items"]) == 1

    get_response = client.get(f"/internships/{internship_id}", headers=auth_headers)
    assert get_response.status_code == 200
    assert get_response.json()["id"] == internship_id
