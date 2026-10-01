from datetime import datetime
from enum import Enum as Pyenum 

from sqlalchemy import ForeignKey, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database.base import Base 
from app.auth.models import User

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
    created_at: Mapped[datetime] = mapped_column(nullable = False, server_default = func.now())
    processing_state: Mapped[STATES] = mapped_column(Enum(STATES, name = "states_enum", values_callable=lambda enum_cls: [e.value for e in enum_cls]),nullable = False, server_default = STATES.UPLOADED.value)

    user = relationship(User)