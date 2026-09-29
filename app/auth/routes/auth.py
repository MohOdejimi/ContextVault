import logging
import os
import jwt

from typing import Annotated
from dotenv import load_dotenv
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from datetime import timedelta
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.auth.models import User
from app.auth.schema import UserCreate, UserOut, Token
from app.auth.security import hash_password, verify_password, create_access_token
from app.database import get_db
from app.config import JWT_ALGORITHM, JWT_SECRET


load_dotenv()
router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger(__name__)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")


@router.post("/register", response_model = UserOut, status_code=status.HTTP_201_CREATED)
def register_user(payload: UserCreate, db: Annotated[Session, Depends(get_db)]):
    user_email =  (payload.email).lower()
    user_password = payload.password
    hashed_password = hash_password(user_password)

    try:
        user_details = User(
            email =  user_email,
            password_hash = hashed_password
        )

        db.add(user_details)
        db.commit()
        db.refresh(user_details)
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists"
        ) from error
    except Exception as error:
        db.rollback()
        logger.exception("Unexpected error during user registration")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Server Error"
        ) from error

    return user_details


@router.post("/login", response_model=Token, status_code=status.HTTP_200_OK)
def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    # test for swagger purposes
    db: Annotated[Session, Depends(get_db)],
):
    user_email = form_data.username.lower()  
    user_password = form_data.password

    try:
        user = db.scalar(select(User).where(User.email == user_email))
    except SQLAlchemyError as error:
        logger.exception("Database error during login")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to process login",
        ) from error

    if not user or not verify_password(user_password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token({"sub": str(user.id)}, timedelta(minutes=30))
    return Token(access_token=access_token, token_type="bearer")


def get_current_user(
    db: Annotated[Session, Depends(get_db)],
    token: Annotated[str, Depends(oauth2_scheme)],
):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except jwt.InvalidTokenError:
        raise credentials_exception
    user = db.scalar(select(User).where(User.id == int(user_id)))
    if user is None:
        raise credentials_exception
    return user

@router.get("/profile")
def profile(current_user = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "email": current_user.email
    }