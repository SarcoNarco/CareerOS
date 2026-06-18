from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from careeros.api.deps import get_db_session, require_api_token
from careeros.schemas.internship import (
    SourceCreateRequest,
    SourceIngestRequest,
    SourceIngestResponse,
    SourceResponse,
)
from careeros.services.ingestion_service import ingest_manual_postings
from careeros.services.source_registry import create_source, list_sources

router = APIRouter(prefix="/sources", tags=["sources"])


@router.get(
    "",
    response_model=list[SourceResponse],
    dependencies=[Depends(require_api_token)],
)
def list_sources_endpoint(
    session: Session = Depends(get_db_session),
) -> list[SourceResponse]:
    return [SourceResponse.model_validate(source) for source in list_sources(session=session)]


@router.post(
    "",
    response_model=SourceResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_api_token)],
)
def create_source_endpoint(
    payload: SourceCreateRequest,
    session: Session = Depends(get_db_session),
) -> SourceResponse:
    source = create_source(session=session, payload=payload)
    return SourceResponse.model_validate(source)


@router.post(
    "/{source_id}/ingest",
    response_model=SourceIngestResponse,
    dependencies=[Depends(require_api_token)],
)
def ingest_source_endpoint(
    source_id: UUID,
    payload: SourceIngestRequest,
    session: Session = Depends(get_db_session),
) -> SourceIngestResponse:
    outcome = ingest_manual_postings(
        session=session,
        source_id=source_id,
        postings=payload.postings,
    )
    return SourceIngestResponse(
        ingestion_run=outcome.ingestion_run,
        created_internships=outcome.created_internships,
        duplicate_count=outcome.duplicate_count,
    )
