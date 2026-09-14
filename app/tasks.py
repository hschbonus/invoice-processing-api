import uuid

from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.celery_app import celery_app
from app.database import SessionLocal
from app.models import ProcessingJob, ProcessingStatus
from app.processing import process_job


@celery_app.task(name="documents.process")
def process_document(job_id: str) -> None:
    with SessionLocal() as session:
        job = session.scalar(
            select(ProcessingJob)
            .options(joinedload(ProcessingJob.document))
            .where(ProcessingJob.id == uuid.UUID(job_id))
        )
        if job is None or job.status in {
            ProcessingStatus.PROCESSING,
            ProcessingStatus.SUCCEEDED,
        }:
            return
        process_job(job, session)
