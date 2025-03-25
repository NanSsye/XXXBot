from pydantic import BaseModel, EmailStr
from typing import Optional

class User(BaseModel):
    """用户模型，简化版本仅包含基本信息"""
    username: str
    email: Optional[EmailStr] = None
    is_admin: bool = False 