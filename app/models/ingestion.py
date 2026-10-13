import uuid

from datetime import datetime
from enum import Enum as Pyenum 
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Enum, CheckConstraint, DateTime, Index, text
from sqlalchemy.orm import Mapped, relationship, mapped_column
from sqlalchemy.sql import func

from app.database.base import Base 

if TYPE_CHECKING:
    from app.models import Document 


class IngestionJobStatus(Pyenum):
    PENDING = 'pending'
    PROCESSING = 'processing'
    COMPLETED = 'completed'
    FAILED = 'failed'

class IngestionJob(Base):
    __tablename__ = "ingestion_jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), nullable = False)
    status: Mapped[IngestionJobStatus] = mapped_column(Enum(IngestionJobStatus, name = "job_states_enum", values_callable=lambda enum_cls: [e.value for e in enum_cls]),nullable = False, server_default = IngestionJobStatus.PENDING.value)
    attempt_count: Mapped[int] = mapped_column(nullable=False, server_default=text('0'))
    max_attempts: Mapped[int] = mapped_column(nullable=False, server_default=text("3"))
    claim_token: Mapped[uuid.UUID] = mapped_column(nullable=True)
    lease_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    document: Mapped["Document"] = relationship(back_populates="ingestion_jobs")

    __table_args__ = (
        CheckConstraint('attempt_count >= 0', name='attempt_count_non_negative'),
        CheckConstraint('attempt_count <= max_attempts', name='attempt_count_valid'),
        CheckConstraint('max_attempts >= 1', name='max_attempts_positive'),
        CheckConstraint(
            '''
            (claim_token IS NULL AND lease_expires_at IS NULL)
            OR
            (claim_token IS NOT NULL AND lease_expires_at IS NOT NULL)
            ''',
            name='claim_token_and_lease_expires_at_consistent'
        ),
        Index(
            "uq_ingestion_jobs_active_document",
            "document_id",
            unique=True,
            postgresql_where=text(
                "status IN ('pending'::job_states_enum, 'processing'::job_states_enum)"
            ),
        )
    )