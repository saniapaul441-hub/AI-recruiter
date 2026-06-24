"""
schemas/auth.py
---------------
Pydantic models define the shape of data coming IN (requests)
and going OUT (responses) from the API.
"""
from pydantic import BaseModel, EmailStr
from app.models.core import UserRole


class RegisterRequest(BaseModel):
    """POST /auth/register"""
    email:     EmailStr
    password:  str
    full_name: str | None = None
    role:      UserRole = UserRole.recruiter


class LoginRequest(BaseModel):
    """POST /auth/login"""
    email:    EmailStr
    password: str


class TokenResponse(BaseModel):
    """Returned after successful login"""
    access_token: str
    token_type:   str = "bearer"
    role:         str
    email:        str


class UserResponse(BaseModel):
    """Safe user info — never includes password_hash"""
    id:        int
    email:     str
    full_name: str | None
    role:      UserRole
    is_active: bool

    model_config = {"from_attributes": True}