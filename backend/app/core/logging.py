"""
Structured Logging Configuration
"""

import logging
import sys
from pathlib import Path
from typing import Optional
from logging.handlers import RotatingFileHandler

from .settings import settings


class StructuredFormatter(logging.Formatter):
    """
    Custom formatter that produces structured log messages
    """
    
    def __init__(self, include_timestamp: bool = True, include_level: bool = True):
        super().__init__()
        self.include_timestamp = include_timestamp
        self.include_level = include_level
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record with structured output"""
        # Extract custom fields
        extra_fields = {}
        for key, value in record.__dict__.items():
            if key not in (
                'name', 'msg', 'args', 'created', 'filename', 'funcName',
                'levelname', 'levelno', 'lineno', 'module', 'msecs',
                'pathname', 'process', 'processName', 'relativeCreated',
                'stack_info', 'exc_info', 'exc_text', 'thread', 'threadName',
                'taskName', 'message'
            ):
                extra_fields[key] = value
        
        # Build structured message
        parts = []
        if self.include_timestamp:
            parts.append(f"[{self.formatTime(record)}]")
        if self.include_level:
            parts.append(f"[{record.levelname}]")
        parts.append(f"[{record.name}]")
        
        # Add message - handle case where msg might not exist
        message = getattr(record, 'msg', '')
        if record.args:
            try:
                message = message % record.args
            except:
                message = str(message) + " " + str(record.args)
        parts.append(message)
        
        # Add extra fields
        if extra_fields:
            field_str = " | ".join(f"{k}={v}" for k, v in extra_fields.items())
            parts.append(f"({field_str})")
        
        return " ".join(parts)


def setup_logging() -> None:
    """
    Configure structured logging for the application
    """
    log_level = getattr(logging, settings.LOG_LEVEL, logging.INFO)
    
    # Create formatter
    formatter = StructuredFormatter()
    
    # Create handlers
    handlers = []
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    handlers.append(console_handler)
    
    # File handler with rotation
    log_dir = settings.TEMP_DIR / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    
    file_handler = RotatingFileHandler(
        filename=log_dir / "pdf_bot.log",
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    handlers.append(file_handler)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Add new handlers
    for handler in handlers:
        root_logger.addHandler(handler)
    
    # Set levels for noisy libraries
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    logging.getLogger("pypdfium2").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger with the specified name
    
    Args:
        name: Name of the logger (typically __name__)
    
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    return logger


class LogContext:
    """
    Context manager for adding extra fields to log records
    """
    
    def __init__(self, logger: logging.Logger, **kwargs):
        self.logger = logger
        self.extra = kwargs
    
    def debug(self, msg: str, **kwargs):
        self.logger.debug(msg, extra={**self.extra, **kwargs})
    
    def info(self, msg: str, **kwargs):
        self.logger.info(msg, extra={**self.extra, **kwargs})
    
    def warning(self, msg: str, **kwargs):
        self.logger.warning(msg, extra={**self.extra, **kwargs})
    
    def error(self, msg: str, **kwargs):
        self.logger.error(msg, extra={**self.extra, **kwargs})
    
    def exception(self, msg: str, **kwargs):
        self.logger.exception(msg, extra={**self.extra, **kwargs})


# Initialize logging on module import
setup_logging()
