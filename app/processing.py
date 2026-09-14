from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.orm import Session

from app.models import DocumentFormat, ProcessingJob, ProcessingStatus
from app.ubl import UblReadError, read_ubl_invoice


def process_job(job: ProcessingJob, session: Session) -> ProcessingJob:
    job.status = ProcessingStatus.PROCESSING
    job.attempts += 1
    job.started_at = datetime.now(UTC)
    job.last_error = None
    session.commit()

    try:
        result = read_ubl_invoice(Path(job.document.storage_path))
    except (OSError, UblReadError) as error:
        job.status = ProcessingStatus.FAILED
        job.last_error = str(error)
        job.completed_at = datetime.now(UTC)
        session.commit()
        session.refresh(job)
        return job

    job.document.detected_format = DocumentFormat.UBL
    job.result = result
    job.status = ProcessingStatus.SUCCEEDED
    job.completed_at = datetime.now(UTC)
    session.commit()
    session.refresh(job)
    return job
