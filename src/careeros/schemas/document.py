from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from careeros.db.models.source_document import DocumentType


class SourceDocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    document_type: DocumentType
    file_name: str
    storage_path: str
    sha256: str
    extracted_text: str | None
    metadata_json: dict[str, str | int | None]
    created_at: datetime
    updated_at: datetime

