import uuid

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.database import Base
from app.models import Document, ProcessingJob, ProcessingStatus
from app.processing import RetryableProcessingError
from app.tasks import MAX_RETRIES, process_document


def build_job() -> tuple[sessionmaker[Session], uuid.UUID]:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    document = Document(
        sha256="b" * 64,
        original_filename="temporarily-unavailable.xml",
        media_type="application/xml",
        size_bytes=512,
        storage_path="missing/temporarily-unavailable.xml",
    )
    job = ProcessingJob(document=document)
    with session_factory() as session:
        session.add(job)
        session.commit()
        job_id = job.id
    return session_factory, job_id


def test_worker_retries_temporary_storage_error(monkeypatch) -> None:
    session_factory, job_id = build_job()
    monkeypatch.setattr("app.tasks.SessionLocal", session_factory)

    with pytest.raises(RetryableProcessingError):
        process_document.run(str(job_id))

    with session_factory() as session:
        job = session.scalar(select(ProcessingJob).where(ProcessingJob.id == job_id))
    assert job is not None
    assert job.status == ProcessingStatus.QUEUED
    assert job.attempts == 1


def test_worker_marks_job_failed_after_retry_limit(monkeypatch) -> None:
    session_factory, job_id = build_job()
    monkeypatch.setattr("app.tasks.SessionLocal", session_factory)

    process_document.push_request(retries=MAX_RETRIES)
    try:
        with pytest.raises(RetryableProcessingError, match="temporarily-unavailable.xml"):
            process_document.run(str(job_id))
    finally:
        process_document.pop_request()

    with session_factory() as session:
        job = session.scalar(select(ProcessingJob).where(ProcessingJob.id == job_id))
    assert job is not None
    assert job.status == ProcessingStatus.FAILED
    assert job.attempts == 1
    assert job.completed_at is not None
