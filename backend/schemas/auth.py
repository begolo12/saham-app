from pydantic import BaseModel
from typing import Optional, Dict, Any


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    token: str
    refresh_token: str
    user: Dict[str, Any]


class UserResponse(BaseModel):
    id: int
    username: str
    role: str
    created_at: str


class RefreshRequest(BaseModel):
    refresh_token: str


class UserCreate(BaseModel):
    username: str
    password: str
    role: str = 'user'
