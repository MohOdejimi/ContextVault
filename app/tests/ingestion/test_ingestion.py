import boto3
import pytest

from pathlib import Path

from sqlalchemy.orm import Session
from sqlalchemy import select, update
from fastapi.testclient import TestClient
from fastapi import status

from app.workers.ingestion_worker import claim_one_job, load_document_metadata, obtain_file_bytes, extract_document
from app.tests.test_database import TestSessionLocal
from app.auth.models import User 
from app.models import IngestionJob, Document, IngestionJobStatus
from app.services.document_extraction import EmptyDocumentError


uploads_dir = Path(__file__).resolve().parents[2] / "upload"

test_pdf_file = Path(uploads_dir) / "test.pdf"
test_one_page_pdf_file = Path(uploads_dir) / "test1.pdf"
test_malformed_pdf = Path(uploads_dir) / "malformed.pdf"
scanned_pdf = Path(uploads_dir) / "scanned_sample.pdf"

def user_registration_helper(client: TestClient, email: str = "TEST@SAMPLE.COM"):
    password = "Securepass2"

    response = client.post(
        "/auth/register",
        json={"email": email, "password": password},
    )
    assert response.status_code == status.HTTP_201_CREATED
    return email, password

def user_login_helper(client: TestClient, email: str, password: str) -> str:
    response = client.post(
        "/auth/login",
        data={"username": email, "password": password},
    )
    assert response.status_code == status.HTTP_200_OK
    return response.json()["access_token"]


def test_empty_queue():
    job = claim_one_job(session_factory = TestSessionLocal)

    assert job is None

def test_successful_claim(client: TestClient, db_session: Session):
    email, password = user_registration_helper(client)
    token = user_login_helper(client, email, password)

    with open(test_pdf_file, 'rb') as f:
        response = client.post('/document',
            headers={"Authorization": f"Bearer {token}"},
            files = {
                "file": (test_pdf_file.name, f, "application/pdf")
            }
        )

    assert response.status_code == status.HTTP_201_CREATED

    user = db_session.scalar(
        select(User)
        .where(User.email == email.lower())
    ) 

    assert user is not None 

    document = db_session.scalar(
        select(Document)
        .where(Document.user_id == user.id)
    )

    assert document is not None 

    job = claim_one_job(TestSessionLocal)

    assert job is not None

    claimed_job = db_session.scalar(
        select(IngestionJob)
        .where(job.job_id == IngestionJob.id)
    )

    assert claimed_job is not None

    assert claimed_job.status == IngestionJobStatus.PROCESSING
    assert claimed_job.attempt_count == 1
    assert claimed_job.claim_token != None
    assert claimed_job.claim_token == job.claim_token
    assert job.doc_id == document.id 


def test_job_at_max_attempts_are_not_claimable(client: TestClient, db_session: Session):
    email, password = user_registration_helper(client)
    token = user_login_helper(client, email, password)

    with open(test_pdf_file, 'rb') as f:
        response = client.post('/document',
            headers={"Authorization": f"Bearer {token}"},
            files = {
                "file": (test_pdf_file.name, f, "application/pdf")
            }
        )

    assert response.status_code == status.HTTP_201_CREATED

    user = db_session.scalar(
        select(User)
        .where(User.email == email.lower())
    ) 

    assert user is not None 

    document = db_session.scalar(
        select(Document)
        .where(Document.user_id == user.id)
    )

    assert document is not None 

    stmt = (
        update(IngestionJob)
        .where(IngestionJob.document_id == document.id)
        .values(attempt_count = 3)
    )

    db_session.execute(stmt)
    db_session.commit()

    job = claim_one_job(TestSessionLocal)

    assert job is None

def test_document_metadata_service(client: TestClient, db_session: Session):
    email, password = user_registration_helper(client)
    token = user_login_helper(client, email, password)

    with open(test_pdf_file, 'rb') as f:
        response = client.post('/document',
            headers={"Authorization": f"Bearer {token}"},
            files = {
                "file": (test_pdf_file.name, f, "application/pdf")
            }
        )

    assert response.status_code == status.HTTP_201_CREATED

    user = db_session.scalar(
        select(User)
        .where(User.email == email.lower())
    ) 

    assert user is not None 

    document = db_session.scalar(
        select(Document)
        .where(Document.user_id == user.id)
    )

    assert document is not None 

    job = claim_one_job(TestSessionLocal)

    document_metadata = load_document_metadata(job.doc_id, TestSessionLocal)

    assert document is not None
    assert document_metadata.original_filename == document.original_filename
    assert document_metadata.s3_key == document.stored_filename
    assert document_metadata.id == document.id
    assert document_metadata.document_size == document.size_in_bytes
    assert document_metadata.content_type == document.content_type

def test_document_storage_service(client: TestClient, db_session: Session, mock_s3_client: boto3.client):
    email, password = user_registration_helper(client)
    token = user_login_helper(client, email, password)

    with open(test_pdf_file, 'rb') as f:
        response = client.post('/document',
            headers={"Authorization": f"Bearer {token}"},
            files = {
                "file": (test_pdf_file.name, f, "application/pdf")
            }
        )

    assert response.status_code == status.HTTP_201_CREATED

    user = db_session.scalar(
        select(User)
        .where(User.email == email.lower())
    ) 

    assert user is not None 

    document = db_session.scalar(
        select(Document)
        .where(Document.user_id == user.id)
    )

    assert document is not None 

    job = claim_one_job(TestSessionLocal)
    assert job is not None

    document_metadata = load_document_metadata(job.doc_id, TestSessionLocal)
    assert document_metadata is not None

    file_bytes = obtain_file_bytes(document_metadata.s3_key, mock_s3_client)

    assert file_bytes is not None 
    assert isinstance(file_bytes, bytes)

def test_one_page_pdf_extraction(client: TestClient, db_session: Session, mock_s3_client: boto3.client):
    email, password = user_registration_helper(client)
    token = user_login_helper(client, email, password)

    with open(test_one_page_pdf_file, 'rb') as f:
        response = client.post('/document',
        
            headers={"Authorization": f"Bearer {token}"},
            files = {
                "file": (test_one_page_pdf_file.name, f, "application/pdf")
            }
        )

    assert response.status_code == status.HTTP_201_CREATED 

    user = db_session.scalar(
        select(User)
        .where(User.email == email.lower())
    )

    assert user is not None

    document = db_session.scalar(
        select(Document)
        .where(Document.user_id == user.id)
    )

    assert document is not None 

    job = claim_one_job(TestSessionLocal)
    assert job is not None 

    document_metadata = load_document_metadata(job.doc_id, TestSessionLocal)
    assert document_metadata is not None 

    file_bytes = obtain_file_bytes(document_metadata.s3_key, mock_s3_client)

    assert file_bytes is not None 

    extracted_segments = extract_document(file_bytes, document_metadata)

    assert extracted_segments is not None

def test_multi_page_pdf_extraction(client: TestClient, db_session: Session, mock_s3_client: boto3.client):
    email, password = user_registration_helper(client)
    token = user_login_helper(client, email, password)

    with open(test_pdf_file, 'rb') as f:
        response = client.post('/document',
        
            headers={"Authorization": f"Bearer {token}"},
            files = {
                "file": (test_pdf_file.name, f, "application/pdf")
            }
        )

    assert response.status_code == status.HTTP_201_CREATED 

    user = db_session.scalar(
        select(User)
        .where(User.email == email.lower())
    )

    assert user is not None

    document = db_session.scalar(
        select(Document)
        .where(Document.user_id == user.id)
    )

    assert document is not None 

    job = claim_one_job(TestSessionLocal)
    assert job is not None 

    document_metadata = load_document_metadata(job.doc_id, TestSessionLocal)
    assert document_metadata is not None 

    file_bytes = obtain_file_bytes(document_metadata.s3_key, mock_s3_client)

    assert file_bytes is not None 

    extracted_segments = extract_document(file_bytes, document_metadata)

    assert extracted_segments is not None

def test_malformed_pdf_extraction(client: TestClient, db_session: Session, mock_s3_client: boto3.client):
    email, password = user_registration_helper(client)
    token = user_login_helper(client, email, password)

    with open(test_malformed_pdf, 'rb') as f:
        response = client.post('/document',
        
            headers={"Authorization": f"Bearer {token}"},
            files = {
                "file": (test_malformed_pdf.name, f, "application/pdf")
            }
        )

    assert response.status_code == status.HTTP_201_CREATED 

    user = db_session.scalar(
        select(User)
        .where(User.email == email.lower())
    )

    assert user is not None

    document = db_session.scalar(
        select(Document)
        .where(Document.user_id == user.id)
    )

    assert document is not None 

    job = claim_one_job(TestSessionLocal)
    assert job is not None 

    document_metadata = load_document_metadata(job.doc_id, TestSessionLocal)
    assert document_metadata is not None 

    file_bytes = obtain_file_bytes(document_metadata.s3_key, mock_s3_client)

    assert file_bytes is not None 

    extracted_segments = extract_document(file_bytes, document_metadata)

    assert extracted_segments is None

def test_scanned_pdf_extraction_without_tesseract(client: TestClient, db_session: Session, mock_s3_client: boto3.client):
    email, password = user_registration_helper(client)
    token = user_login_helper(client, email, password)

    with open(scanned_pdf, 'rb') as f:
        response = client.post('/document',
        
            headers={"Authorization": f"Bearer {token}"},
            files = {
                "file": (scanned_pdf.name, f, "application/pdf")
            }
        )

    assert response.status_code == status.HTTP_201_CREATED 

    user = db_session.scalar(
        select(User)
        .where(User.email == email.lower())
    )

    assert user is not None

    document = db_session.scalar(
        select(Document)
        .where(Document.user_id == user.id)
    )

    assert document is not None 

    job = claim_one_job(TestSessionLocal)
    assert job is not None 

    document_metadata = load_document_metadata(job.doc_id, TestSessionLocal)
    assert document_metadata is not None 

    file_bytes = obtain_file_bytes(document_metadata.s3_key, mock_s3_client)

    assert file_bytes is not None 

    with pytest.raises(EmptyDocumentError):
        extract_document(file_bytes, document_metadata)
   