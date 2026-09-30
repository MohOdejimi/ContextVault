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

def test_user_login(client: TestClient):
    password = 'Securepass1'
    email = "TEXT@SAMPLE.COM"

    registration_response = client.post('/auth/register', 
        json = {
            "email": email,
            "password": password
        }                                  
    )

    assert registration_response.status_code == status.HTTP_201_CREATED

    login_response = client.post('/auth/login',
        data = {
            "username": email, 
            "password": password
        }                
    )

    data = login_response.json()

    assert login_response.status_code == status.HTTP_200_OK
    assert set(data) == {"access_token", "token_type"}

def test_valid_token_returns_correct_profile(
    client: TestClient,
) -> None:
    email = "profile@example.com"
    password = "Securepass1"

    registration_response = client.post(
        "/auth/register",
        json={
            "email": email,
            "password": password,
        },
    )

    assert registration_response.status_code == status.HTTP_201_CREATED

    registered_user = registration_response.json()

    login_response = client.post(
        "/auth/login",
        data={
            "username": email,
            "password": password,
        },
    )

    assert login_response.status_code == status.HTTP_200_OK

    login_data = login_response.json()

    assert "access_token" in login_data
    assert login_data["token_type"] == "bearer"

    access_token = login_data["access_token"]

    profile_response = client.get(
        "/auth/profile",
        headers={
            "Authorization": f"Bearer {access_token}",
        },
    )

    assert profile_response.status_code == status.HTTP_200_OK

    profile_data = profile_response.json()

    assert profile_data == {
        "id": registered_user["id"],
        "email": email,
    }

    assert "password" not in profile_data
    assert "password_hash" not in profile_data