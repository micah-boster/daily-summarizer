from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel


class CommitmentStatus(StrEnum):
    OPEN = "open"
    COMPLETED = "completed"
    DEFERRED = "deferred"


class Commitment(BaseModel):
    id: str
    owner: str
    description: str
    by_when: datetime | None = None
    status: CommitmentStatus = CommitmentStatus.OPEN
    source_id: str
    source_type: str
    source_context: str = ""
    extracted_at: datetime | None = None
