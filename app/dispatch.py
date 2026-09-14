import uuid
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import ProcessingJob, ProcessingStatus
from app.processing import process_job


def enqueue_job(job_id: uuid.UUID) -> None:
    from app.tasks import process_document

    process_document.delay(str(job_id))


def dispatch_job(
    job: ProcessingJob, settings: Settings, session: Session
) -> ProcessingJob:
    if settings.processing_mode == "sync":
        return process_job(job, session)

    try:
        enqueue_job(job.id)
    except Exception as error:
        job.status = ProcessingStatus.FAILED
        job.last_error = "The processing job could not be enqueued."
        job.completed_at = datetime.now(UTC)
        session.commit()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "message": "The processing service is temporarily unavailable.",
                "job_id": str(job.id),
            },
        ) from error

    return job
