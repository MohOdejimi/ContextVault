import re 
from pydantic import BaseModel, EmailStr, field_validator
from datetime import datetime 

class UserCreate(BaseModel):
    email: EmailStr
    password: str 

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError('Password length must be greater than 8')
        if not re.search(r'[A-Z]', v):
            raise ValueError('Password must contain an upperCase letter')
        if not re.search(r'[a-z]', v):
            raise ValueError('Password must contain a lowercase letter')
        if not re.search(r'[0-9]', v):
            raise ValueError('Password must contain a numeric character')

        return v 

class UserLogin(BaseModel):
    email: EmailStr
    password: str 

class UserOut(BaseModel):
    id: str
    email: EmailStr
