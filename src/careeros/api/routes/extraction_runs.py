from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from careeros.api.deps import get_db_session, require_api_token
from careeros.schemas.extraction import ExtractionDiagnosticsResponse
from careeros.services.extraction_service import get_extraction_run_diagnostics

router = APIRouter(prefix="/extraction-runs", tags=["extraction-runs"])


@router.get(
    "/{extraction_run_id}/diagnostics",
    response_model=ExtractionDiagnosticsResponse,
    dependencies=[Depends(require_api_token)],
)
def get_extraction_run_diagnostics_endpoint(
    extraction_run_id: UUID,
    session: Session = Depends(get_db_session),
) -> ExtractionDiagnosticsResponse:
    return get_extraction_run_diagnostics(
        session=session,
        extraction_run_id=extraction_run_id,
    )
