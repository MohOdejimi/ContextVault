import bcrypt
import jwt 
import os

from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone


load_dotenv()

def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    encoded_password = password.encode('utf-8')
    hashed_password = bcrypt.hashpw(encoded_password, salt)
    return hashed_password.decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    encoded_hashed_password = hashed_password.encode('utf-8')       
    encoded_plain_password = plain_password.encode('utf-8')

    return bcrypt.checkpw(encoded_plain_password, encoded_hashed_password)

def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=15))
    to_encode.update({
        "exp": expire
    })
    encoded_jwt = jwt.encode(to_encode, os.getenv("jwt_secret"), os.getenv("algorithm"))
    return encoded_jwt