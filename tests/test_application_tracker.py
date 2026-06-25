from __future__ import annotations

from uuid import UUID

from sqlalchemy import select

from careeros.db.models.application import ApplicationRecord


def _create_profile(client, auth_headers) -> str:
    response = client.post(
        "/profiles",
        headers=auth_headers,
        json={
            "display_name": "Application Test Student",
            "email": "application-test@example.com",
            "timezone": "Asia/Kolkata",
            "target_roles": ["Backend Intern"],
            "target_locations": ["Remote"],
            "work_preferences": {},
        },
    )
    return response.json()["id"]


def _create_source(client, auth_headers) -> str:
    response = client.post(
        "/sources",
        headers=auth_headers,
        json={
            "name": "Application Tracker Test Source",
            "source_type": "manual",
            "base_url": "https://applications.example.com",
            "is_active": True,
            "policy_status": "allowed",
        },
    )
    return response.json()["id"]


def _create_internship(client, auth_headers, source_id: str) -> str:
    response = client.post(
        f"/sources/{source_id}/ingest",
        headers=auth_headers,
        json={
            "postings": [
                {
                    "external_id": "application-backend-001",
                    "source_url": "https://applications.example.com/jobs/backend",
                    "title": "Backend Intern",
                    "company_name": "Application Labs",
                    "company_domain": "applications.example.com",
                    "description": "Build backend APIs using Python and FastAPI.",
                    "requirements": "Python, FastAPI, PostgreSQL, Docker.",
                    "responsibilities": "Build and test backend services.",
                    "application_url": "https://applications.example.com/jobs/backend/apply",
                    "location": "Worldwide Remote",
                    "work_mode": "Remote",
                }
            ]
        },
    )
    return response.json()["created_internships"][0]["id"]


def _create_application_fixture(client, auth_headers) -> tuple[str, str]:
    profile_id = _create_profile(client, auth_headers)
    source_id = _create_source(client, auth_headers)
    internship_id = _create_internship(client, auth_headers, source_id)
    return profile_id, internship_id


def test_save_application(client, auth_headers, db_session) -> None:
    profile_id, internship_id = _create_application_fixture(client, auth_headers)

    response = client.post(
        "/applications",
        headers=auth_headers,
        json={
            "profile_id": profile_id,
            "internship_id": internship_id,
            "status": "saved",
            "priority": 2,
            "notes": "Looks promising.",
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["profile_id"] == profile_id
    assert payload["internship_id"] == internship_id
    assert payload["status"] == "saved"
    assert payload["priority"] == 2
    assert payload["notes"] == "Looks promising."
    assert payload["internship"]["title"] == "Backend Intern"

    persisted = db_session.scalar(
        select(ApplicationRecord).where(ApplicationRecord.id == UUID(payload["id"]))
    )
    assert persisted is not None


def test_duplicate_application_returns_existing_record(client, auth_headers, db_session) -> None:
    profile_id, internship_id = _create_application_fixture(client, auth_headers)
    payload = {
        "profile_id": profile_id,
        "internship_id": internship_id,
        "status": "saved",
        "priority": 3,
    }

    first = client.post("/applications", headers=auth_headers, json=payload)
    second = client.post("/applications", headers=auth_headers, json=payload)

    assert first.status_code == 201
    assert second.status_code == 200
    assert second.json()["id"] == first.json()["id"]
    assert len(list(db_session.scalars(select(ApplicationRecord)))) == 1


def test_status_update_sets_applied_at(client, auth_headers) -> None:
    profile_id, internship_id = _create_application_fixture(client, auth_headers)
    create_response = client.post(
        "/applications",
        headers=auth_headers,
        json={"profile_id": profile_id, "internship_id": internship_id},
    )
    application_id = create_response.json()["id"]

    response = client.patch(
        f"/applications/{application_id}",
        headers=auth_headers,
        json={"status": "applied"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "applied"
    assert response.json()["applied_at"] is not None


def test_notes_update(client, auth_headers) -> None:
    profile_id, internship_id = _create_application_fixture(client, auth_headers)
    create_response = client.post(
        "/applications",
        headers=auth_headers,
        json={"profile_id": profile_id, "internship_id": internship_id},
    )
    application_id = create_response.json()["id"]

    response = client.patch(
        f"/applications/{application_id}",
        headers=auth_headers,
        json={"notes": "Follow up with recruiter next week.", "priority": 1},
    )

    assert response.status_code == 200
    assert response.json()["notes"] == "Follow up with recruiter next week."
    assert response.json()["priority"] == 1


def test_list_applications_by_profile(client, auth_headers) -> None:
    profile_id, internship_id = _create_application_fixture(client, auth_headers)
    client.post(
        "/applications",
        headers=auth_headers,
        json={
            "profile_id": profile_id,
            "internship_id": internship_id,
            "status": "interview",
            "priority": 1,
        },
    )

    response = client.get(
        f"/profiles/{profile_id}/applications",
        headers=auth_headers,
        params={"status": "interview", "priority": 1},
    )

    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["status"] == "interview"
    assert items[0]["priority"] == 1


def test_delete_archives_application(client, auth_headers, db_session) -> None:
    profile_id, internship_id = _create_application_fixture(client, auth_headers)
    create_response = client.post(
        "/applications",
        headers=auth_headers,
        json={"profile_id": profile_id, "internship_id": internship_id},
    )
    application_id = create_response.json()["id"]

    response = client.delete(f"/applications/{application_id}", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["status"] == "closed"
    archived = db_session.scalar(
        select(ApplicationRecord).where(ApplicationRecord.id == UUID(application_id))
    )
    assert archived is not None
    assert archived.status == "closed"

    new_response = client.post(
        "/applications",
        headers=auth_headers,
        json={"profile_id": profile_id, "internship_id": internship_id},
    )
    assert new_response.status_code == 201
    assert new_response.json()["id"] != application_id
