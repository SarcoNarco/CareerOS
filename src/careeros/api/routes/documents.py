from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from sqlalchemy.orm import Session

from careeros.api.deps import get_db_session, get_settings, require_api_token
from careeros.core.config import Settings
from careeros.db.models.source_document import DocumentType
from careeros.schemas.document import SourceDocumentResponse
from careeros.schemas.extraction import ExtractionSummaryResponse
from careeros.services.document_service import store_source_document
from careeros.services.extraction_service import extract_document_candidates

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post(
    "/upload",
    response_model=SourceDocumentResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_api_token)],
)
async def upload_document_endpoint(
    profile_id: Annotated[UUID, Form()],
    file: Annotated[UploadFile, File()],
    document_type: Annotated[DocumentType, Form()] = DocumentType.RESUME,
    session: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> SourceDocumentResponse:
    document = await store_source_document(
        session=session,
        profile_id=profile_id,
        upload=file,
        document_type=document_type,
        storage_root=settings.storage_root,
        max_upload_size_bytes=settings.max_upload_size_bytes,
    )
    return SourceDocumentResponse.model_validate(document)


@router.post(
    "/{document_id}/extract",
    response_model=ExtractionSummaryResponse,
    dependencies=[Depends(require_api_token)],
)
def extract_document_endpoint(
    document_id: UUID,
    session: Session = Depends(get_db_session),
) -> ExtractionSummaryResponse:
    return extract_document_candidates(session=session, document_id=document_id)
