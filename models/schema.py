import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, List

from sqlmodel import Field, SQLModel
from sqlalchemy import Column, DateTime, JSON
from sqlalchemy.sql import func


class JobStatus(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Job(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    collection_id: str
    resources: List[str] = Field(default_factory=list, sa_column=Column(JSON))
    ref: Optional[str] = None
    status: JobStatus = Field(default=JobStatus.PENDING)
    error_message: Optional[str] = None
    
    # Use sqlalchemy's server_default to handle timestamps at the DB layer implicitly
    created_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now())
    )
    updated_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    )



class Tradition(SQLModel, table=True):
    id: int = Field(default=None, primary_key=True)
    collection_id: str
    resources: List[str] = Field(default_factory=list, sa_column=Column(JSON))
    number_of_included_sections: int
    result_path: str
    job_id: Optional[uuid.UUID] = Field(default=None, foreign_key="job.id")
    
    created_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now())
    )

    updated_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    )
