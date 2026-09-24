from fastapi import APIRouter, status, HTTPException
from pymongo.errors import DuplicateKeyError

from auth.database import user_collections
from auth.schema import UserCreate, UserLogin, UserOut
from auth.security import hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])
@router.post('/register', response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register_user(payload: UserCreate):
    user_details = {
        "email": payload.email.lower(),
        "password": hash_password(payload.password)
    }

    try:
        user_doc = await user_collections.insert_one(user_details)
    except DuplicateKeyError:
        raise HTTPException(
            status_code = status.HTTP_409_CONFLICT,
            detail = "AN account with this email exists"
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Something unexpected happens, please try again"
        )

    return {
        "id": str(user_doc.inserted_id),
        "email": user_details["email"]
    }