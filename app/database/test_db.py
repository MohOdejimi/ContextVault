from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.database.connection import engine

try:
    with engine.connect() as connection:
        result = connection.execute(text("SELECT 1"))
        print("Connected to database")
        print("Test query result:", result.scalar_one())
except SQLAlchemyError as e:
    print(f"Unable to connect to database {e}")
