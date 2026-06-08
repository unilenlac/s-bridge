import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, List

from sqlmodel import Field, SQLModel
from sqlalchemy import Column, DateTime, JSON
from sqlalchemy.sql import func

# ==============================================================================
# Database Schema Definitions (SQLModel + SQLAlchemy Hybrid Pattern)
# ==============================================================================
# This application uses both SQLModel and SQLAlchemy in a complementary hybrid pattern:
#
# 1. SQLModel:
#    - Serves as the high-level schema defintion.
#    - Since it inherits from Pydantic BaseModel, SQLModel allows these classes to
#      serve as FastAPI request/response validators and serialization schemas,
#      avoiding code duplication.
#
# 2. SQLAlchemy:
#    - Used directly to configure advanced DB features that SQLModel's high-level
#      attributes don't expose natively (e.g. JSON fields, timezone-aware datetimes,
#      and server-side defaults).
# ==============================================================================


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
    collection_url: str

    # We specify an explicit SQLAlchemy Column(JSON) here because standard SQLModel/Pydantic
    # collections do not map to SQLite/Postgres JSON fields natively without this mapping.
    resources: List[str] = Field(default_factory=list, sa_column=Column(JSON))
    ref: Optional[str] = None
    status: JobStatus = Field(default=JobStatus.PENDING)
    error_message: Optional[str] = None

    # SQLModel doesn't expose database-level triggers/hooks.
    # We use SQLAlchemy Columns to handle automatic timezone-aware DB timestamps.
    created_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now()),
    )
    updated_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(
            DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
        ),
    )


class Tradition(SQLModel, table=True):
    id: int = Field(default=None, primary_key=True)
    collection_url: str
    collection_id: str
    resources: List[str] = Field(default_factory=list, sa_column=Column(JSON))
    number_of_included_sections: int
    result_path: str
    job_id: Optional[uuid.UUID] = Field(default=None, foreign_key="job.id")

    # We use SQLAlchemy Columns to handle automatic timezone-aware DB timestamps.
    created_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now()),
    )

    updated_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(
            DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
        ),
    )
