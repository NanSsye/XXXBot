from fastapi import APIRouter

from app.api.endpoints import auth, plugins

api_router = APIRouter()

# 包含认证路由
api_router.include_router(auth.router, prefix="/auth", tags=["认证"])

# 包含插件路由
api_router.include_router(plugins.router, prefix="/plugins", tags=["插件管理"]) 