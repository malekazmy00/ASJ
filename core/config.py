# core/config.py
from pydantic_settings import BaseSettings
from pydantic import Field, field_validator
from typing import Optional, Tuple, List
from pathlib import Path

class Settings(BaseSettings):
    # Base
    BASE_DIR: Path = Path(__file__).parent.parent
    APP_NAME: str = "ASJ Medical Systems Store"
    APP_VERSION: str = "2.0.0"
    ENVIRONMENT: str = Field(default="production", env="ENVIRONMENT")
    
    # Security
    SECRET_KEY: str = Field(default="", env="SECRET_KEY")
    
    @field_validator('SECRET_KEY')
    @classmethod
    def validate_secret_key(cls, v: str) -> str:
        if not v or v == "":
            raise ValueError("SECRET_KEY must be set in environment variables")
        if len(v) < 32:
            raise ValueError("SECRET_KEY must be at least 32 characters")
        return v
    
    # Session
    SESSION_TYPE: str = Field(default="memory", env="SESSION_TYPE")
    SESSION_TIMEOUT: int = 3600
    SESSION_REFRESH: int = 900
    JWT_ALGORITHM: str = "HS256"
    
    # Redis (اختياري)
    REDIS_URL: Optional[str] = Field(default=None, env="REDIS_URL")
    REDIS_PREFIX: str = "session:"
    
    # Database (يدعم Supabase / PostgreSQL أو SQLite محلياً)
    DATABASE_URL: Optional[str] = Field(default=None, env="DATABASE_URL")
    DB_PATH: Path = BASE_DIR / "warehouse_system.db"
    DB_POOL_SIZE: int = 5
    DB_TIMEOUT: int = 30
    DB_ECHO: bool = False
    
    # API Keys
    GEMINI_API_KEY: Optional[str] = Field(default=None, env="GEMINI_API_KEY")
    
    # AI Settings (ترتيب تصاعدي: الأرخص والأسرع أولاً، ثم الأقوى عند الحاجة)
    LITE_AI_MODEL: str = "gemini-3.5-flash-lite"
    FAST_AI_MODEL: str = "gemini-3.6-flash"
    STRONG_AI_MODEL: str = "gemini-3.1-pro"
    AI_RETRY_COUNT: int = 3
    AI_RETRY_DELAY: float = 1.0
    
# Supabase Storage (لتخزين صور القطع بشكل دائم)
    SUPABASE_URL: Optional[str] = Field(default=None, env="SUPABASE_URL")
    SUPABASE_KEY: Optional[str] = Field(default=None, env="SUPABASE_KEY")
    SUPABASE_STORAGE_BUCKET: str = "part-images"

    # Image Settings
    MAX_IMAGE_SIZE: Tuple[int, int] = (1024, 1024)
    IMAGE_QUALITY: int = 80
    IMAGE_FORMAT: str = "JPEG"
    MAX_IMAGE_MB: int = 10
    MAX_IMAGE_PIXELS: int = 50_000_000
    
    # OCR Settings
    OCR_LANGUAGES: List[str] = ["ara", "eng"]
    MIN_IMAGE_DIMENSION: int = 250
    BLUR_VARIANCE_THRESHOLD: int = 15
    OCR_TIMEOUT: int = 30
    
    # Search
    PAGE_SIZE: int = 50
    MAX_SEARCH_TERM: int = 1000
    
    # Rate Limiting
    RATE_LIMIT_TYPE: str = Field(default="memory", env="RATE_LIMIT_TYPE")
    RATE_LIMIT_LOGIN: int = 5
    RATE_LIMIT_WINDOW: int = 60
    
    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FILE: Path = BASE_DIR / "logs" / "app.log"
    LOG_MAX_SIZE: int = 10 * 1024 * 1024
    LOG_BACKUP_COUNT: int = 5
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True

settings = Settings()
