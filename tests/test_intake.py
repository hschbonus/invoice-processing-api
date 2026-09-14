import uuid
from collections.abc import Iterator
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import Settings, get_settings
from app.database import Base, get_db
from app.main import app
from app.models import Document, DocumentFormat, ProcessingJob, ProcessingStatus

SAMPLES = Path(__file__).parents[1] / "samples" / "ubl"


def new_storage_dir() -> Path:
    return Path(".test-storage") / str(uuid.uuid4())


def remove_storage_dir(storage_dir: Path) -> None:
    if storage_dir.exists():
        for stored_file in storage_dir.iterdir():
            stored_file.unlink()
        storage_dir.rmdir()
    parent = storage_dir.parent
    if parent.exists() and not any(parent.iterdir()):
        parent.rmdir()


def build_client(
    storage_dir: Path, processing_mode: str = "sync"
) -> tuple[TestClient, sessionmaker[Session]]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    testing_session = sessionmaker(bind=engine, expire_on_commit=False)

    def override_db() -> Iterator[Session]:
        with testing_session() as session:
            yield session

    def override_settings() -> Settings:
        return Settings(
            app_env="test",
            database_url="sqlite://",
            storage_dir=storage_dir,
            max_upload_bytes=4096,
            processing_mode=processing_mode,
        )

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_settings] = override_settings
    return TestClient(app), testing_session


def test_async_upload_enqueues_job_and_returns_queued_status(monkeypatch) -> None:
    storage_dir = new_storage_dir()
    client, testing_session = build_client(storage_dir, processing_mode="celery")
    enqueued_job_ids: list[uuid.UUID] = []
    monkeypatch.setattr("app.dispatch.enqueue_job", enqueued_job_ids.append)

    response = client.post(
        "/v1/documents",
        files={
            "file": (
                "invoice.xml",
                (SAMPLES / "valid-invoice.xml").read_bytes(),
                "application/xml",
            )
        },
    )

    assert response.status_code == 202
    assert response.json()["status"] == "queued"
    assert enqueued_job_ids == [uuid.UUID(response.json()["job_id"])]
    with testing_session() as session:
        job = session.scalar(select(ProcessingJob))
    assert job is not None
    assert job.status == ProcessingStatus.QUEUED
    assert job.attempts == 0
    app.dependency_overrides.clear()
    remove_storage_dir(storage_dir)


def test_upload_persists_document_and_queues_job() -> None:
    storage_dir = new_storage_dir()
    client, testing_session = build_client(storage_dir)

    response = client.post(
        "/v1/documents",
        files={
            "file": (
                "invoice.xml",
                (SAMPLES / "valid-invoice.xml").read_bytes(),
                "application/xml",
            )
        },
    )

    assert response.status_code == 202
    assert response.json()["status"] == "succeeded"
    assert response.json()["deduplicated"] is False
    with testing_session() as session:
        document = session.scalar(select(Document))
        job = session.scalar(select(ProcessingJob))

    assert document is not None
    assert document.original_filename == "invoice.xml"
    assert document.detected_format == DocumentFormat.UBL
    assert job is not None
    assert str(job.id) == response.json()["job_id"]
    assert job.status == ProcessingStatus.SUCCEEDED
    assert job.attempts == 1
    assert job.result is not None
    assert job.result["validation_status"] == "valid"

    detail_response = client.get(f"/v1/jobs/{job.id}")
    assert detail_response.status_code == 200
    assert detail_response.json()["result"]["invoice"]["amounts"]["gross"] == "120.00"
    app.dependency_overrides.clear()
    remove_storage_dir(storage_dir)


def test_duplicate_upload_reuses_existing_document_and_job() -> None:
    storage_dir = new_storage_dir()
    client, testing_session = build_client(storage_dir)
    sample = (SAMPLES / "valid-invoice.xml").read_bytes()

    first_response = client.post(
        "/v1/documents",
        files={"file": ("first-name.xml", sample, "application/xml")},
    )
    second_response = client.post(
        "/v1/documents",
        files={"file": ("second-name.xml", sample, "application/xml")},
    )

    assert first_response.status_code == 202
    assert second_response.status_code == 202
    assert second_response.json()["deduplicated"] is True
    assert second_response.json()["document_id"] == first_response.json()["document_id"]
    assert second_response.json()["job_id"] == first_response.json()["job_id"]
    with testing_session() as session:
        assert len(session.scalars(select(Document)).all()) == 1
        assert len(session.scalars(select(ProcessingJob)).all()) == 1
    assert len(list(storage_dir.iterdir())) == 1
    app.dependency_overrides.clear()
    remove_storage_dir(storage_dir)


def test_upload_returns_structured_business_anomalies() -> None:
    storage_dir = new_storage_dir()
    client, _ = build_client(storage_dir)

    response = client.post(
        "/v1/documents",
        files={
            "file": (
                "invalid.xml",
                (SAMPLES / "invalid-business-invoice.xml").read_bytes(),
                "application/xml",
            )
        },
    )
    detail_response = client.get(f"/v1/jobs/{response.json()['job_id']}")

    assert response.status_code == 202
    assert response.json()["status"] == "succeeded"
    assert detail_response.json()["result"]["validation_status"] == "invalid"
    anomaly_codes = {
        anomaly["code"] for anomaly in detail_response.json()["result"]["anomalies"]
    }
    assert anomaly_codes == {
        "amounts_do_not_balance",
        "invalid_currency",
        "invalid_date",
        "required_field_missing",
    }
    app.dependency_overrides.clear()
    remove_storage_dir(storage_dir)


def test_malformed_xml_creates_failed_job() -> None:
    storage_dir = new_storage_dir()
    client, _ = build_client(storage_dir)

    response = client.post(
        "/v1/documents",
        files={
            "file": (
                "malformed.xml",
                (SAMPLES / "malformed-invoice.xml").read_bytes(),
                "application/xml",
            )
        },
    )
    detail_response = client.get(f"/v1/jobs/{response.json()['job_id']}")

    assert response.status_code == 202
    assert response.json()["status"] == "failed"
    assert detail_response.json()["result"] is None
    assert detail_response.json()["last_error"] == "The document is not well-formed XML."
    app.dependency_overrides.clear()
    remove_storage_dir(storage_dir)


def test_upload_rejects_non_xml_file() -> None:
    storage_dir = new_storage_dir()
    client, _ = build_client(storage_dir)

    response = client.post(
        "/v1/documents",
        files={"file": ("invoice.pdf", b"not a pdf", "application/pdf")},
    )

    assert response.status_code == 415
    assert not storage_dir.exists()
    app.dependency_overrides.clear()


def test_upload_rejects_oversized_file_and_removes_partial_copy() -> None:
    storage_dir = new_storage_dir()
    client, _ = build_client(storage_dir)

    response = client.post(
        "/v1/documents",
        files={"file": ("invoice.xml", b"x" * 4097, "application/xml")},
    )

    assert response.status_code == 413
    assert list(storage_dir.iterdir()) == []
    app.dependency_overrides.clear()
    remove_storage_dir(storage_dir)
