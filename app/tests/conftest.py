import pytest

from sqlalchemy import create_engine, delete
from sqlalchemy.orm import Session, sessionmaker 
from collections.abc import Generator 
from fastapi.testclient import TestClient

from app.config import TEST_DATABASE_URL
from app.database import get_db as production_get_db 
from app.auth.models import User 
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

@pytest.fixture()
def client() -> Generator[TestClient, None, None]:
    app.dependency_overrides[production_get_db] = override_get_db 

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.pop(production_get_db, None)

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