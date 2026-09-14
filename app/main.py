import uuid
from typing import Annotated

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.database import get_db
from app.dispatch import dispatch_job
from app.intake import save_document
from app.models import ProcessingJob, ProcessingStatus
from app.schemas import IntakeAccepted, JobDetail

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    description=(
        "Personal technical case study for intake and validation of fictional "
        "structured supplier invoices."
    ),
    version="0.1.0",
)


@app.get("/health", tags=["operations"])
def health() -> dict[str, str]:
    return {"status": "ok", "environment": settings.app_env}


@app.post(
    "/v1/documents",
    response_model=IntakeAccepted,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["documents"],
)
def create_document(
    file: Annotated[UploadFile, File(description="A structured UBL XML invoice")],
    db: Annotated[Session, Depends(get_db)],
    request_settings: Annotated[Settings, Depends(get_settings)],
) -> IntakeAccepted:
    job, deduplicated = save_document(file, request_settings, db)
    if not deduplicated:
        job = dispatch_job(job, request_settings, db)
    return IntakeAccepted(
        document_id=job.document_id,
        job_id=job.id,
        status=job.status,
        deduplicated=deduplicated,
    )


@app.get(
    "/v1/jobs/{job_id}",
    response_model=JobDetail,
    tags=["jobs"],
)
def get_job(
    job_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
) -> ProcessingJob:
    job = db.scalar(select(ProcessingJob).where(ProcessingJob.id == job_id))
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")
    return job


@app.post(
    "/v1/jobs/{job_id}/retry",
    response_model=JobDetail,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["jobs"],
)
def retry_job(
    job_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    request_settings: Annotated[Settings, Depends(get_settings)],
) -> ProcessingJob:
    job = db.scalar(select(ProcessingJob).where(ProcessingJob.id == job_id))
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")
    if job.status != ProcessingStatus.FAILED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only a failed job can be retried.",
        )

    job.status = ProcessingStatus.QUEUED
    job.last_error = None
    job.completed_at = None
    db.commit()
    db.refresh(job)
    return dispatch_job(job, request_settings, db)
