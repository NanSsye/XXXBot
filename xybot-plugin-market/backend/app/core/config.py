import os
import secrets
from typing import List, Optional
from pydantic import AnyHttpUrl
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # 基本设置
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = os.getenv("SECRET_KEY", secrets.token_urlsafe(32))
    # 默认60分钟
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    
    # CORS设置
    CORS_ORIGINS: List[str] = [
        "http://localhost",
        "http://localhost:8080",
        "http://localhost:3000",
        "*"  # 添加通配符允许所有源（仅用于开发环境）
    ]
    
    # 数据库配置
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./sql_app.db")
    
    # 管理员配置
    ADMIN_USERNAME: str = os.getenv("ADMIN_USERNAME", "admin")
    ADMIN_PASSWORD: str = os.getenv("ADMIN_PASSWORD", "admin")
    ADMIN_EMAIL: str = os.getenv("ADMIN_EMAIL", "admin@example.com")
    
    # 服务器设置
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    
    # 默认为开发环境
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    
    # 插件市场相关配置
    PLUGIN_DIR: str = os.getenv("PLUGIN_DIR", "./plugins")
    TEMP_DIR: str = os.getenv("TEMP_DIR", "./temp")
    
    class Config:
        case_sensitive = True
        env_file = ".env"

settings = Settings() 