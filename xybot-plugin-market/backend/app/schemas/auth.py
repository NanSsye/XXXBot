from typing import Optional
from pydantic import BaseModel

class LoginRequest(BaseModel):
    username: str
    password: str

class LoginResponse(BaseModel):
    success: bool
    access_token: Optional[str] = None
    token_type: Optional[str] = None
    error: Optional[str] = None 