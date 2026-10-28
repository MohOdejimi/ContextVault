import uuid
import logging

from dataclasses import dataclass
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.exc import DatabaseError

from app.services.ingestion_jobs import claim_pending_job
from app.services.document_metadata import load_document
from app.services.document_storage import get_raw_file_bytes
from app.services.document_extraction import extract_document
from app.storage.s3 import get_s3_client
from app.core.database.connection import SessionLocal 
from app.core.config import S3_BUCKET_NAME


logger = logging.getLogger(__name__)

@dataclass
class JobData:
    job_id: int
    doc_id: int 
    claim_token: uuid.UUID

def claim_one_job(
        session_factory: sessionmaker[Session] = SessionLocal
):
    data = None

    with session_factory.begin() as db_session:
        job = claim_pending_job(db_session)

        if job is not None:
            data = JobData(
                job_id = job.id,
                doc_id = job.document_id,
                claim_token = job.claim_token 
            )

    return data


@dataclass(frozen=True)
class DocumentMeta:
    id: int
    s3_key: str
    content_type: str
    original_filename: str | None
    document_size: int

def load_document_metadata(doc_id: int, session_factory=SessionLocal) -> DocumentMeta:
    with session_factory.begin() as db:
        document = load_document(db, doc_id)
        if document is None:
            raise LookupError(f"document {doc_id} not found")
        return DocumentMeta(
            id=document.id,
            s3_key=document.stored_filename,
            content_type=document.content_type,
            original_filename=document.original_filename,
            document_size=document.size_in_bytes
        )

        
def obtain_file_bytes(
        s3_key,
        s3_client = None
    ):
    try:
        file_bytes = get_raw_file_bytes(s3_key, s3_client)
        return file_bytes
    except Exception:
        logger.exception("Failed to obtain file bytes for %s", s3_key)
        raise

