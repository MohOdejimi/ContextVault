import pytest
import boto3

from sqlalchemy import create_engine, delete
from sqlalchemy.orm import Session, sessionmaker 
from collections.abc import Generator 
from fastapi.testclient import TestClient
from typing import Annotated
from moto import mock_aws

from app.config import (
    TEST_DATABASE_URL,
    AWS_ACCESS_KEY_ID,
    AWS_SECRET_ACCESS_KEY,
    AWS_DEFAULT_REGION,
)
from app.database import get_db as production_get_db 
from app.auth.models import User 
from app.storage.s3 import get_s3_client as production_s3_client
from app.main import app 

if not TEST_DATABASE_URL:
    raise RuntimeError("TEST_DATABASE_URL is not configured")

test_engine = create_engine(
    TEST_DATABASE_URL,
    pool_pre_ping=True
)

TestSessionLocal = sessionmaker(
    bind=test_engine,
    expire_on_commit=False,
    autoflush=False
)

def override_get_db() -> Generator[Session, None, None]:
    db: Session = TestSessionLocal()
    try:
        yield db 
    finally:
        db.close()
    
@pytest.fixture(autouse=True)
def aws_credentials(monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", AWS_ACCESS_KEY_ID)
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", AWS_SECRET_ACCESS_KEY)
    monkeypatch.setenv("AWS_DEFAULT_REGION", AWS_DEFAULT_REGION)

@pytest.fixture
def aws(aws_credentials):
    with mock_aws():
        yield

@pytest.fixture
def mock_s3_client(aws, monkeypatch) -> Generator[boto3.client, None, None]:
    s3_client = boto3.client('s3', region_name=AWS_DEFAULT_REGION)
    s3_client.create_bucket(Bucket="contextvault-test-uploads")
    monkeypatch.setenv("S3_BUCKET_NAME", "contextvault-test-uploads")
    yield s3_client
    s3_client.close()

@pytest.fixture
def client(mock_s3_client) -> Generator[TestClient, None, None]:
    app.dependency_overrides[production_get_db] = override_get_db 
    def callable() -> Generator[boto3.client, None, None]:
        yield mock_s3_client

    app.dependency_overrides[production_s3_client] = callable

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.pop(production_get_db, None)
    app.dependency_overrides.pop(production_s3_client, None)


@pytest.fixture(autouse=True)
def clean_database() -> Generator[None, None, None]:
    with TestSessionLocal() as session:
        session.execute(delete(User))
        session.commit()

        yield 

    with TestSessionLocal() as session:
        session.execute(delete(User))
        session.commit()

@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    with TestSessionLocal() as session:
        yield session 