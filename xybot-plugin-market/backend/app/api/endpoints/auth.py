from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm

from app.core.config import settings
from app.core.security import create_access_token, verify_password
from app.schemas.auth import LoginRequest, LoginResponse

router = APIRouter()

@router.post("/login", response_model=LoginResponse)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    管理员登录 (表单方式)
    """
    # 直接比较明文密码，因为配置中的密码也是明文的
    if form_data.username != settings.ADMIN_USERNAME or form_data.password != settings.ADMIN_PASSWORD:
        return LoginResponse(
            success=False,
            error="用户名或密码不正确"
        )
    
    # 创建访问令牌
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        subject=form_data.username, expires_delta=access_token_expires
    )
    
    return LoginResponse(
        success=True,
        access_token=access_token,
        token_type="bearer"
    )

@router.post("/json-login", response_model=LoginResponse)
async def json_login(login_data: LoginRequest):
    """
    管理员登录 (JSON方式)
    """
    # 直接比较明文密码，因为配置中的密码也是明文的
    if login_data.username != settings.ADMIN_USERNAME or login_data.password != settings.ADMIN_PASSWORD:
        return LoginResponse(
            success=False,
            error="用户名或密码不正确"
        )
    
    # 创建访问令牌
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        subject=login_data.username, expires_delta=access_token_expires
    )
    
    return LoginResponse(
        success=True,
        access_token=access_token,
        token_type="bearer"
    ) 