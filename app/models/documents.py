from datetime import datetime
from enum import Enum as Pyenum 
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Enum, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.core.database.base import Base 
from app.auth.models import User

if TYPE_CHECKING:
    from app.models.ingestion import IngestionJob

class STATES(Pyenum):
    UPLOADED = 'uploaded'
    PROCESSING = "processing"
    FAILED = 'failed'
    READY = 'ready'

class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete='CASCADE'), nullable = False)
    original_filename: Mapped[str] = mapped_column(nullable = False)
    stored_filename: Mapped[str] = mapped_column(nullable = False, unique = True)
    content_type: Mapped[str] = mapped_column(nullable = False)
    size_in_bytes: Mapped[int] = mapped_column(nullable = False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable = False, server_default = func.now())
    processing_state: Mapped[STATES] = mapped_column(Enum(STATES, name = "states_enum", values_callable=lambda enum_cls: [e.value for e in enum_cls]),nullable = False, server_default = STATES.UPLOADED.value)
    ingestion_jobs: Mapped[list["IngestionJob"]] = relationship(back_populates="document", passive_deletes=True, cascade="all, delete-orphan")

    user = relationship(User)