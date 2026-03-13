"""Authentication schemas"""
from pydantic import BaseModel, EmailStr, Field


class SignupRequest(BaseModel):
    """Signup request schema"""
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=72, description="Password must be between 8 and 72 characters")
    full_name: str = Field(..., min_length=1)
    confirm_password: str = Field(..., min_length=8, max_length=72)


class LoginRequest(BaseModel):
    """Login request schema"""
    email: EmailStr
    password: str = Field(..., max_length=72)


class TokenResponse(BaseModel):
    """Token response schema"""
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    """User response schema"""
    id: str
    email: str
    full_name: str
    
    class Config:
        from_attributes = True

