from io import BytesIO
from uuid import UUID

from sqlalchemy import select

from careeros.db.models.source_document import SourceDocument


def test_upload_document_stores_metadata(client, auth_headers, db_session) -> None:
    profile_response = client.post(
        "/profiles",
        headers=auth_headers,
        json={
            "display_name": "Sarosh",
            "email": "sarosh@example.com",
            "timezone": "Asia/Kolkata",
            "target_roles": [],
            "target_locations": [],
            "work_preferences": {},
        },
    )
    profile_id = profile_response.json()["id"]

    upload_response = client.post(
        "/documents/upload",
        headers=auth_headers,
        data={"profile_id": profile_id, "document_type": "resume"},
        files={
            "file": ("resume.pdf", BytesIO(b"%PDF-1.4 fake resume content"), "application/pdf")
        },
    )

    assert upload_response.status_code == 201
    payload = upload_response.json()
    assert payload["file_name"] == "resume.pdf"
    assert payload["metadata_json"]["size_bytes"] > 0

    document = db_session.scalar(
        select(SourceDocument).where(SourceDocument.id == UUID(payload["id"]))
    )
    assert document is not None
    assert document.sha256 == payload["sha256"]
