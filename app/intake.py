import hashlib
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import Document, ProcessingJob
from app.processing import process_job

ALLOWED_MEDIA_TYPES = {"application/xml", "text/xml"}
CHUNK_SIZE = 64 * 1024


def _existing_job(sha256: str, session: Session) -> ProcessingJob | None:
    return session.scalar(
        select(ProcessingJob)
        .join(Document)
        .where(Document.sha256 == sha256)
        .order_by(ProcessingJob.created_at.desc())
        .limit(1)
    )


def save_document(
    file: UploadFile, settings: Settings, session: Session
) -> tuple[ProcessingJob, bool]:
    if file.content_type not in ALLOWED_MEDIA_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Only XML documents are accepted.",
        )

    filename = Path(file.filename or "").name
    if not filename or Path(filename).suffix.lower() != ".xml":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="The uploaded document must have an .xml filename.",
        )

    document_id = uuid.uuid4()
    settings.storage_dir.mkdir(parents=True, exist_ok=True)
    destination = settings.storage_dir / f"{document_id}.xml"
    digest = hashlib.sha256()
    size_bytes = 0

    try:
        with destination.open("xb") as stored_file:
            while chunk := file.file.read(CHUNK_SIZE):
                size_bytes += len(chunk)
                if size_bytes > settings.max_upload_bytes:
                    raise HTTPException(
                        status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                        detail=f"Document exceeds the {settings.max_upload_bytes}-byte limit.",
                    )
                digest.update(chunk)
                stored_file.write(chunk)

        if size_bytes == 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="The uploaded document is empty.",
            )

        sha256 = digest.hexdigest()
        existing_job = _existing_job(sha256, session)
        if existing_job is not None:
            destination.unlink(missing_ok=True)
            return existing_job, True

        document = Document(
            id=document_id,
            sha256=sha256,
            original_filename=filename,
            media_type=file.content_type,
            size_bytes=size_bytes,
            storage_path=str(destination),
        )
        job = ProcessingJob(document=document)
        session.add(job)
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
            destination.unlink(missing_ok=True)
            existing_job = _existing_job(sha256, session)
            if existing_job is None:
                raise
            return existing_job, True
        session.refresh(job)
        return process_job(job, session), False
    except Exception:
        session.rollback()
        destination.unlink(missing_ok=True)
        raise
