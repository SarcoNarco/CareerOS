from io import BytesIO
from uuid import UUID

from sqlalchemy import select

from careeros.db.models.embedding import (
    EmbeddableEntityType,
    EmbeddingRebuildQueue,
    EntityEmbedding,
)
from careeros.db.models.internship import Internship
from careeros.services.embedding_provider import DeterministicEmbeddingProvider
from careeros.services.embedding_service import embed_internship, process_rebuild_queue, queue_all_rebuilds


def _create_profile_with_approved_claim(client, auth_headers) -> tuple[str, str]:
    profile_response = client.post(
        "/profiles",
        headers=auth_headers,
        json={
            "display_name": "Sarosh",
            "email": "sarosh-embeddings@example.com",
            "timezone": "Asia/Kolkata",
            "target_roles": ["Backend Intern", "ML Intern"],
            "target_locations": ["Remote"],
            "work_preferences": {},
        },
    )
    profile_id = profile_response.json()["id"]

    resume_text = """PROJECTS
CareerOS
- Built FastAPI PostgreSQL Docker backend services for internship discovery
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
    approve_response = client.post(
        f"/fact-candidates/{claim_candidate['id']}/approve",
        headers=auth_headers,
        json={"notes": "Verified for embedding tests."},
    )
    claim_id = approve_response.json()["approved_claim"]["id"]
    return profile_id, claim_id


def _create_source(client, auth_headers) -> str:
    response = client.post(
        "/sources",
        headers=auth_headers,
        json={
            "name": "Embedding Test Source",
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
                    "location": "Worldwide Remote",
                    "work_mode": "Remote",
                }
            ]
        },
    )
    internship_id = response.json()["created_internships"][0]["id"]
    client.post(f"/internships/{internship_id}/normalize", headers=auth_headers)
    return internship_id


def test_profile_embedding_creation(client, auth_headers, db_session) -> None:
    profile_id, claim_id = _create_profile_with_approved_claim(client, auth_headers)

    response = client.post(f"/profiles/{profile_id}/embed", headers=auth_headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload["profile_id"] == profile_id
    assert len(payload["embeddings"]) == 1
    assert payload["embeddings"][0]["created"] is True

    embedding = db_session.scalar(
        select(EntityEmbedding).where(
            EntityEmbedding.entity_type == EmbeddableEntityType.APPROVED_CLAIM,
            EntityEmbedding.entity_id == UUID(claim_id),
            EntityEmbedding.is_active.is_(True),
        )
    )
    assert embedding is not None
    assert embedding.content_hash
    assert embedding.embedding_version.startswith("deterministic:")
    assert len(embedding.embedding) == 64


def test_internship_embedding_invalidation_on_content_change(
    client,
    auth_headers,
    db_session,
) -> None:
    source_id = _create_source(client, auth_headers)
    internship_id = _create_internship(
        client,
        auth_headers,
        source_id,
        external_id="backend-embed-001",
        title="Backend Intern",
        description="Build FastAPI PostgreSQL Docker services.",
    )

    first_response = client.post(f"/internships/{internship_id}/embed", headers=auth_headers)
    assert first_response.status_code == 200
    assert first_response.json()["created"] is True

    internship = db_session.scalar(select(Internship).where(Internship.id == UUID(internship_id)))
    assert internship is not None
    internship.description = "Build FastAPI PostgreSQL Docker services and Python APIs."
    db_session.commit()

    second_response = client.post(f"/internships/{internship_id}/embed", headers=auth_headers)
    assert second_response.status_code == 200
    assert second_response.json()["created"] is True

    embeddings = list(
        db_session.scalars(
            select(EntityEmbedding).where(
                EntityEmbedding.entity_type == EmbeddableEntityType.INTERNSHIP,
                EntityEmbedding.entity_id == UUID(internship_id),
            )
        )
    )
    assert len(embeddings) == 2
    assert sum(1 for embedding in embeddings if embedding.is_active) == 1
    assert any(embedding.invalidation_reason == "content_changed" for embedding in embeddings)


def test_internship_embedding_invalidation_on_version_change(
    client,
    auth_headers,
    db_session,
    app,
) -> None:
    source_id = _create_source(client, auth_headers)
    internship_id = _create_internship(
        client,
        auth_headers,
        source_id,
        external_id="backend-embed-version-001",
        title="Backend Intern",
        description="Build FastAPI PostgreSQL Docker services.",
    )

    first_result = embed_internship(
        session=db_session,
        internship_id=UUID(internship_id),
        provider=app.state.embedding_provider,
    )
    assert first_result.created is True

    versioned_provider = DeterministicEmbeddingProvider(
        model_name="deterministic-local",
        embedding_version="deterministic:64:v2",
        dimension=64,
    )
    second_result = embed_internship(
        session=db_session,
        internship_id=UUID(internship_id),
        provider=versioned_provider,
    )

    assert second_result.created is True
    embeddings = list(
        db_session.scalars(
            select(EntityEmbedding).where(
                EntityEmbedding.entity_type == EmbeddableEntityType.INTERNSHIP,
                EntityEmbedding.entity_id == UUID(internship_id),
            )
        )
    )
    assert len(embeddings) == 2
    assert sum(1 for embedding in embeddings if embedding.is_active) == 1
    assert any(embedding.invalidation_reason == "embedding_version_changed" for embedding in embeddings)


def test_rebuild_queue_processing(client, auth_headers, db_session, app) -> None:
    profile_id, _ = _create_profile_with_approved_claim(client, auth_headers)
    source_id = _create_source(client, auth_headers)
    _create_internship(
        client,
        auth_headers,
        source_id,
        external_id="rebuild-001",
        title="ML Engineer Intern",
        description="Machine learning internship using Python and PyTorch.",
    )

    queued_count = queue_all_rebuilds(session=db_session, reason="test_rebuild")
    db_session.commit()

    result = process_rebuild_queue(
        session=db_session,
        provider=app.state.embedding_provider,
        limit=10,
    )

    assert queued_count >= 2
    assert result.processed_count == queued_count
    assert result.created_count >= 2
    assert db_session.scalar(
        select(EmbeddingRebuildQueue).where(EmbeddingRebuildQueue.processed_at.is_(None))
    ) is None

    profile_response = client.post(f"/profiles/{profile_id}/embed", headers=auth_headers)
    assert profile_response.status_code == 200


def test_candidate_internship_retrieval_uses_semantic_similarity(client, auth_headers) -> None:
    profile_id, _ = _create_profile_with_approved_claim(client, auth_headers)
    source_id = _create_source(client, auth_headers)
    backend_id = _create_internship(
        client,
        auth_headers,
        source_id,
        external_id="backend-retrieval-001",
        title="Backend Intern",
        description="Build FastAPI PostgreSQL Docker backend services with Python APIs.",
    )
    data_id = _create_internship(
        client,
        auth_headers,
        source_id,
        external_id="data-retrieval-001",
        title="Data Analyst Intern",
        description="Create dashboards using spreadsheets, reporting workflows, and business metrics.",
    )

    client.post(f"/profiles/{profile_id}/embed", headers=auth_headers)
    client.post(f"/internships/{backend_id}/embed", headers=auth_headers)
    client.post(f"/internships/{data_id}/embed", headers=auth_headers)

    response = client.get(
        f"/profiles/{profile_id}/candidate-internships",
        headers=auth_headers,
        params={"limit": 2},
    )

    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 2
    assert items[0]["internship"]["id"] == backend_id
    assert items[0]["similarity_score"] >= items[1]["similarity_score"]
