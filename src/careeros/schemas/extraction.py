from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from careeros.db.models.fact_staging import ExtractionStatus


class ExtractionSummaryResponse(BaseModel):
    extraction_run_id: UUID
    source_document_id: UUID
    status: ExtractionStatus
    extracted_text_length: int
    candidate_count: int
    evidence_span_count: int
    candidates_by_kind: dict[str, int]
    started_at: datetime
    completed_at: datetime | None

