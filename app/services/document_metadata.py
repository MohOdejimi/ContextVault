import logging

from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.exc import DatabaseError

from app.models import Document

logger = logging.getLogger(__name__)

def load_document(db: Session, doc_id: int):
    try:
        stmt = select(Document).where(Document.id == doc_id)
        document = db.execute(stmt).scalars().first()

        return document
    except DatabaseError as e:
        logger.exception("Unexpected DB error during lookup")
        raise 
    except Exception:
        raise    
