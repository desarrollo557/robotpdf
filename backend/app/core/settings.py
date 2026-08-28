"""
Application Settings using Pydantic Settings Management
"""

from pathlib import Path
from typing import List, Optional
import multiprocessing
import os
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables or .env file
    """
    
    # Pydantic Settings Configuration
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    # ===========================================================================
    # DeepSeek API Configuration
    # ===========================================================================
    DEEPSEEK_API_KEY: str = "your-api-key-here"
    DEEPSEEK_API_BASE: str = "https://api.deepseek.com"
    DEEPSEEK_MODEL: str = "deepseek-chat"
    
    # ===========================================================================
    # Database Configuration
    # ===========================================================================
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/pdf_resolution_bot"
    DATABASE_POOL_SIZE: int = 20
    DATABASE_POOL_TIMEOUT: int = 30
    
    # ===========================================================================
    # File Storage Configuration
    # ===========================================================================
    UPLOAD_DIR: Path = Path("C:/pdf_bot/uploads")
    OUTPUT_DIR: Path = Path("C:/pdf_bot/output")
    TEMP_DIR: Path = Path("C:/pdf_bot/temp")
    MAX_UPLOAD_SIZE_MB: int = 1024
    AUTO_CLEANUP_DAYS: int = 30
    
    # ===========================================================================
    # PDF Rendering Configuration
    # ===========================================================================
    RENDER_DPI: int = 150
    RENDER_SCALE: float = 1.0
    RENDER_COLOR_SPACE: str = "gray"  # gray, rgb, cmyk
    
    # ===========================================================================
    # OCR Configuration
    # ===========================================================================
    OCR_ENGINE: str = "auto"  # auto, tesseract, paddleocr
    OCR_CONFIDENCE_THRESHOLD: float = 0.7
    OCR_FALLBACK_ENABLED: bool = True
    TESSERACT_PATH: Optional[str] = None
    TESSERACT_LANG: str = "spa"
    PADDLEOCR_USE_GPU: bool = False
    PADDLEOCR_LANG: str = "spa"
    
    # ===========================================================================
    # AI Classification Configuration
    # ===========================================================================
    AI_BATCH_SIZE: int = 8
    AI_MAX_CONCURRENCY: int = 50
    AI_RETRY_COUNT: int = 3
    AI_RETRY_BACKOFF_BASE: float = 1.0
    AI_RETRY_BACKOFF_MAX: float = 30.0
    AI_TIMEOUT: float = 120.0
    
    # ===========================================================================
    # Processing Pipeline Configuration
    # ===========================================================================
    WORKER_PROCESS_COUNT: int = 0  # 0 = auto (cpu_count - 1)
    STAGE1_QUEUE_SIZE: int = 1000
    STAGE2_QUEUE_SIZE: int = 1000
    STAGE3_QUEUE_SIZE: int = 1000
    
    # ===========================================================================
    # WebSocket Configuration
    # ===========================================================================
    WS_PING_INTERVAL: int = 20
    WS_PING_TIMEOUT: int = 60
    PROGRESS_UPDATE_INTERVAL_MS: int = 2000
    
    # ===========================================================================
    # Web Server Configuration
    # ===========================================================================
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    WORKERS: int = 1
    LOG_LEVEL: str = "INFO"
    
    # ===========================================================================
    # Security Configuration
    # ===========================================================================
    SECRET_KEY: str = "change-this-in-production-to-a-strong-secret-key"
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"
    ALLOWED_FILE_TYPES: str = ".pdf"
    
    # ===========================================================================
    # Prometheus Metrics Configuration
    # ===========================================================================
    PROMETHEUS_ENABLED: bool = True
    PROMETHEUS_PORT: int = 9090
    
    @property
    def allowed_file_extensions(self) -> List[str]:
        """Parse allowed file types into a list"""
        return [ext.strip().lower() for ext in self.ALLOWED_FILE_TYPES.split(",")]
    
    @property
    def cors_origins_list(self) -> List[str]:
        """Parse CORS origins into a list"""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]
    
    @property
    def max_upload_size_bytes(self) -> int:
        """Convert max upload size from MB to bytes"""
        return self.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    
    @property
    def actual_worker_process_count(self) -> int:
        """Get actual worker process count (auto if 0)"""
        if self.WORKER_PROCESS_COUNT <= 0:
            cpu_count = multiprocessing.cpu_count()
            return max(1, cpu_count - 1)
        return self.WORKER_PROCESS_COUNT
    
    @field_validator("UPLOAD_DIR", "OUTPUT_DIR", "TEMP_DIR", mode="before")
    @classmethod
    def ensure_path(cls, v):
        """Convert string paths to Path objects"""
        if isinstance(v, str):
            return Path(v)
        return v
    
    @field_validator("LOG_LEVEL", mode="before")
    @classmethod
    def validate_log_level(cls, v):
        """Validate log level"""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(f"LOG_LEVEL must be one of {valid_levels}")
        return v.upper()
    
    def ensure_directories(self):
        """Create necessary directories if they don't exist"""
        directories = [self.UPLOAD_DIR, self.OUTPUT_DIR, self.TEMP_DIR]
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)


# Global settings instance
settings = Settings()

# Ensure directories exist on import
settings.ensure_directories()
