from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.database import Base
from app.models import Document, DocumentFormat, ProcessingJob, ProcessingStatus


def test_document_and_processing_job_are_persisted() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)

    document = Document(
        sha256="a" * 64,
        original_filename="invoice.xml",
        media_type="application/xml",
        size_bytes=512,
        storage_path="documents/example.xml",
        detected_format=DocumentFormat.UBL,
    )
    document.jobs.append(ProcessingJob())

    with Session(engine) as session:
        session.add(document)
        session.commit()
        document_id = document.id
        job = session.scalar(select(ProcessingJob))

    assert job is not None
    assert job.status == ProcessingStatus.QUEUED
    assert job.document_id == document_id
