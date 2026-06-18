import hashlib
from pathlib import Path
from uuid import UUID

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from careeros.db.models.profile import Profile
from careeros.db.models.source_document import DocumentType, SourceDocument
from careeros.services.document_extractor import extract_text_from_bytes
from careeros.utils.files import sanitize_filename


async def store_source_document(
    session: Session,
    profile_id: UUID,
    upload: UploadFile,
    document_type: DocumentType,
    storage_root: Path,
    max_upload_size_bytes: int,
) -> SourceDocument:
    profile = session.scalar(select(Profile).where(Profile.id == profile_id))
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found.",
        )

    original_name = sanitize_filename(upload.filename or "upload.bin")
    document = SourceDocument(
        user_id=profile.user_id,
        document_type=document_type,
        file_name=original_name,
        storage_path="",
        sha256="",
        extracted_text=None,
        metadata_json={},
    )
    session.add(document)
    session.flush()

    storage_root.mkdir(parents=True, exist_ok=True)
    storage_path = storage_root / f"{document.id}_{original_name}"

    sha256 = hashlib.sha256()
    size_bytes = 0
    content_chunks: list[bytes] = []

    with storage_path.open("wb") as destination:
        while True:
            chunk = await upload.read(1024 * 1024)
            if not chunk:
                break
            size_bytes += len(chunk)
            if size_bytes > max_upload_size_bytes:
                destination.close()
                storage_path.unlink(missing_ok=True)
                session.rollback()
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail="Uploaded file exceeds the configured size limit.",
                )
            sha256.update(chunk)
            content_chunks.append(chunk)
            destination.write(chunk)

    await upload.close()

    raw_content = b"".join(content_chunks)
    extracted_text = extract_text_from_bytes(
        file_name=original_name,
        content_type=upload.content_type,
        content=raw_content,
    )

    document.storage_path = str(storage_path.resolve())
    document.sha256 = sha256.hexdigest()
    document.extracted_text = extracted_text
    document.metadata_json = {
        "content_type": upload.content_type,
        "original_filename": original_name,
        "size_bytes": size_bytes,
    }

    session.commit()
    session.refresh(document)
    return document
