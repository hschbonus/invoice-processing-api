import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.models import ProcessingStatus


class IntakeAccepted(BaseModel):
    document_id: uuid.UUID
    job_id: uuid.UUID
    status: ProcessingStatus
    deduplicated: bool


class JobDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    document_id: uuid.UUID
    status: ProcessingStatus
    attempts: int
    result: dict[str, Any] | None
    last_error: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
