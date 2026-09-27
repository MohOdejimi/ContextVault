import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.models import Users
from app.auth.schema import UserCreate, UserOut
from app.auth.security import hash_password
from app.database import get_db

router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger(__name__)

@router.post("/register", response_model = UserOut, status_code=status.HTTP_201_CREATED)
def register_user(payload: UserCreate, db: Annotated[Session, Depends(get_db)]):
    user_email =  (payload.email).lower()
    user_password = payload.password
    hashed_password = hash_password(user_password)

    try:
        user_details = Users(
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
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        ) from error

    return user_details

