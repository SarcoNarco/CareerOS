from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from careeros.api.deps import get_db_session, get_embedding_provider, require_api_token
from careeros.schemas.embedding import (
    CandidateInternshipListResponse,
    CandidateInternshipResponse,
    EmbedEntityResponse,
    EmbedProfileResponse,
    EntityEmbeddingResponse,
    RebuildEmbeddingsRequest,
    RebuildEmbeddingsResponse,
)
from careeros.schemas.internship import InternshipResponse
from careeros.services.embedding_provider import EmbeddingProvider
from careeros.services.embedding_service import (
    embed_internship,
    embed_profile_claims,
    rebuild_all_embeddings,
)
from careeros.services.retrieval_service import retrieve_candidate_internships

router = APIRouter(tags=["embeddings"])


@router.post(
    "/embeddings/rebuild",
    response_model=RebuildEmbeddingsResponse,
    dependencies=[Depends(require_api_token)],
)
def rebuild_embeddings_endpoint(
    payload: RebuildEmbeddingsRequest,
    session: Session = Depends(get_db_session),
    provider: EmbeddingProvider = Depends(get_embedding_provider),
) -> RebuildEmbeddingsResponse:
    if payload.process:
        result = rebuild_all_embeddings(
            session=session,
            provider=provider,
            limit=payload.limit,
        )
        return RebuildEmbeddingsResponse(
            queued_count=result.queued_count,
            processed_count=result.processed_count,
            created_count=result.created_count,
        )

    from careeros.services.embedding_service import queue_all_rebuilds

    queued_count = queue_all_rebuilds(session=session)
    session.commit()
    return RebuildEmbeddingsResponse(
        queued_count=queued_count,
        processed_count=0,
        created_count=0,
    )


@router.post(
    "/profiles/{profile_id}/embed",
    response_model=EmbedProfileResponse,
    dependencies=[Depends(require_api_token)],
)
def embed_profile_endpoint(
    profile_id: UUID,
    session: Session = Depends(get_db_session),
    provider: EmbeddingProvider = Depends(get_embedding_provider),
) -> EmbedProfileResponse:
    results = embed_profile_claims(
        session=session,
        profile_id=profile_id,
        provider=provider,
    )
    return EmbedProfileResponse(
        profile_id=profile_id,
        embeddings=[
            EmbedEntityResponse(
                embedding=EntityEmbeddingResponse.model_validate(result.embedding),
                created=result.created,
            )
            for result in results
        ],
    )


@router.post(
    "/internships/{internship_id}/embed",
    response_model=EmbedEntityResponse,
    dependencies=[Depends(require_api_token)],
)
def embed_internship_endpoint(
    internship_id: UUID,
    session: Session = Depends(get_db_session),
    provider: EmbeddingProvider = Depends(get_embedding_provider),
) -> EmbedEntityResponse:
    result = embed_internship(
        session=session,
        internship_id=internship_id,
        provider=provider,
    )
    return EmbedEntityResponse(
        embedding=EntityEmbeddingResponse.model_validate(result.embedding),
        created=result.created,
    )


@router.get(
    "/profiles/{profile_id}/candidate-internships",
    response_model=CandidateInternshipListResponse,
    dependencies=[Depends(require_api_token)],
)
def retrieve_candidate_internships_endpoint(
    profile_id: UUID,
    limit: int = Query(default=10, ge=1, le=100),
    session: Session = Depends(get_db_session),
    provider: EmbeddingProvider = Depends(get_embedding_provider),
) -> CandidateInternshipListResponse:
    candidates = retrieve_candidate_internships(
        session=session,
        profile_id=profile_id,
        provider=provider,
        limit=limit,
    )
    return CandidateInternshipListResponse(
        profile_id=profile_id,
        items=[
            CandidateInternshipResponse(
                internship=InternshipResponse.model_validate(candidate.internship),
                similarity_score=candidate.similarity_score,
            )
            for candidate in candidates
        ],
    )
