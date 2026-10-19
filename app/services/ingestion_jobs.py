import uuid 
import logging

from sqlalchemy import select, text, func
from sqlalchemy.orm import Session


from app.models.ingestion import IngestionJob 


logger = logging.getLogger(__name__)

def claim_pending_job(db: Session):
    try:
        stmt = select(IngestionJob).where(IngestionJob.status == 'pending',IngestionJob.attempt_count < IngestionJob.max_attempts).order_by(IngestionJob.created_at, IngestionJob.id).limit(1).with_for_update(skip_locked=True)
        

        job = db.execute(stmt).scalars().first()

        if job is not None:
            job.attempt_count += 1
            job.status = 'processing'
            job.claim_token = uuid.uuid4()
            job.created_at = func.now()
            job.lease_expires_at = func.now() + text("Interval '7 minutes'")

        return job
    except Exception as e:
        raise