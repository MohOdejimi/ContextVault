from fastapi.testclient import TestClient 
from fastapi import status

from sqlalchemy.orm import Session 
from sqlalchemy import select

from app.auth.models import User 
from app.auth.security import verify_password


def test_user_registered_successfully(client: TestClient, db_session: Session):
    password = 'Securepass1'
    email = 'TEXT@SAMPLE.COM'

    response = client.post('/auth/register', 
        json = {
            "email": email,
            "password": password
        }
    )

    data = response.json()

    assert response.status_code == status.HTTP_201_CREATED
    assert isinstance(data["id"], int)
    assert set(data) == {"id", "email"}
    assert data["email"] == "text@sample.com"

    stored_user = db_session.scalar(
        select(User).where(User.email == "text@sample.com")
    )

    assert stored_user is not None 
    assert stored_user.password_hash != password
    assert verify_password(password, stored_user.password_hash)