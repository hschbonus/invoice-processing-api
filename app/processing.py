from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.orm import Session

from app.models import DocumentFormat, ProcessingJob, ProcessingStatus
from app.ubl import UblReadError, read_ubl_invoice


class RetryableProcessingError(Exception):
    """A temporary infrastructure error that can be retried safely."""


def fail_job(
    job: ProcessingJob, session: Session, error: str
) -> ProcessingJob:
    job.status = ProcessingStatus.FAILED
    job.last_error = error
    job.completed_at = datetime.now(UTC)
    session.commit()
    session.refresh(job)
    return job


def process_job(
    job: ProcessingJob,
    session: Session,
    *,
    retry_transient_errors: bool = False,
) -> ProcessingJob:
    job.status = ProcessingStatus.PROCESSING
    job.attempts += 1
    job.started_at = datetime.now(UTC)
    job.last_error = None
    session.commit()

    try:
        result = read_ubl_invoice(Path(job.document.storage_path))
    except OSError as error:
        if not retry_transient_errors:
            return fail_job(job, session, str(error))
        job.status = ProcessingStatus.QUEUED
        job.last_error = str(error)
        job.completed_at = None
        session.commit()
        session.refresh(job)
        raise RetryableProcessingError(str(error)) from error
    except UblReadError as error:
        return fail_job(job, session, str(error))

    job.document.detected_format = DocumentFormat.UBL
    job.result = result
    job.status = ProcessingStatus.SUCCEEDED
    job.completed_at = datetime.now(UTC)
    session.commit()
    session.refresh(job)
    return job
