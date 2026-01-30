"""
Application configuration using Pydantic settings.
"""

import os
from functools import lru_cache

try:
    from pydantic_settings import BaseSettings
except ImportError:
    from pydantic import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # API Keys
    google_api_key: str = ""
    
    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False
    
    # CORS
    cors_origins: str = "http://localhost:5173,http://localhost:3000"
    
    # Models
    default_model: str = "gemini-2.5-flash"
    pro_model: str = "gemini-2.5-pro"
    
    # Logging
    environment: str = "development"  # development | staging | production
    log_level: str = "INFO"
    enable_file_logging: bool = False
    log_max_bytes: int = 10485760  # 10MB
    log_backup_count: int = 5
    
    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",")]
    
    @property
    def is_production(self) -> bool:
        return self.environment == "production"
    
    @property
    def is_development(self) -> bool:
        return self.environment == "development"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
