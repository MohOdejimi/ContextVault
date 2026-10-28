from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import TEST_DATABASE_URL

test_engine = create_engine(
    TEST_DATABASE_URL,
    pool_pre_ping=True
)

TestSessionLocal = sessionmaker(
    bind=test_engine,
    expire_on_commit=False,
    autoflush=False
)