import uuid

from dataclasses import dataclass
from sqlalchemy.orm import Session, sessionmaker

from app.services.ingestion_jobs import claim_pending_job
from app.database.connection import SessionLocal 

@dataclass
class JobData:
    job_id: int
    doc_id: int 
    claim_token: uuid.UUID



def claim_one_job(
        session_factory: sessionmaker[Session] = SessionLocal
):
    data = None

    with session_factory.begin() as db:
        job = claim_pending_job(db)

        if job is not None:
            data = JobData(
                job_id = job.id,
                doc_id = job.document_id,
                claim_token = job.claim_token 
            )

    return data