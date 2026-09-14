import uuid

from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.celery_app import celery_app
from app.database import SessionLocal
from app.models import ProcessingJob, ProcessingStatus
from app.processing import RetryableProcessingError, fail_job, process_job

MAX_RETRIES = 3


@celery_app.task(bind=True, name="documents.process", max_retries=MAX_RETRIES)
def process_document(self, job_id: str) -> None:
    with SessionLocal() as session:
        job = session.scalar(
            select(ProcessingJob)
            .options(joinedload(ProcessingJob.document))
            .where(ProcessingJob.id == uuid.UUID(job_id))
        )
        if job is None or job.status == ProcessingStatus.SUCCEEDED:
            return
        try:
            process_job(job, session, retry_transient_errors=True)
        except RetryableProcessingError as error:
            if self.request.retries >= MAX_RETRIES:
                fail_job(job, session, str(error))
                raise
            countdown = 2**self.request.retries
            raise self.retry(exc=error, countdown=countdown) from error
