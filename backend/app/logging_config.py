"""
Production-ready logging configuration for Kanso.AI backend.

Features:
- Structured JSON logging for production
- Human-readable console logging for development
- Request correlation IDs for distributed tracing
- Log rotation with size limits
- Configurable log levels per module
- Performance timing decorators
"""

import logging
import logging.handlers
import json
import sys
import time
import uuid
import os
from datetime import datetime
from functools import wraps
from typing import Any, Callable
from contextvars import ContextVar
from pathlib import Path

from .config import get_settings

# Context variable for request correlation ID
correlation_id_var: ContextVar[str] = ContextVar('correlation_id', default='no-correlation-id')


def get_correlation_id() -> str:
    """Get the current correlation ID from context."""
    return correlation_id_var.get()


def set_correlation_id(correlation_id: str = None) -> str:
    """Set a correlation ID in the current context. Generates one if not provided."""
    cid = correlation_id or str(uuid.uuid4())[:8]
    correlation_id_var.set(cid)
    return cid


class JSONFormatter(logging.Formatter):
    """
    JSON formatter for structured logging in production.
    Outputs logs in a format suitable for log aggregation systems like
    ELK Stack, Datadog, or CloudWatch.
    """
    
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "correlation_id": get_correlation_id(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        # Add extra fields if present
        if hasattr(record, 'extra_data'):
            log_data["data"] = record.extra_data
        
        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "message": str(record.exc_info[1]) if record.exc_info[1] else None,
                "traceback": self.formatException(record.exc_info)
            }
        
        # Add duration if present (for performance logging)
        if hasattr(record, 'duration_ms'):
            log_data["duration_ms"] = record.duration_ms
        
        return json.dumps(log_data, default=str)


class ColoredConsoleFormatter(logging.Formatter):
    """
    Human-readable colored formatter for development console output.
    """
    
    COLORS = {
        'DEBUG': '\033[36m',     # Cyan
        'INFO': '\033[32m',      # Green
        'WARNING': '\033[33m',   # Yellow
        'ERROR': '\033[31m',     # Red
        'CRITICAL': '\033[41m',  # Red background
    }
    RESET = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    
    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelname, '')
        cid = get_correlation_id()
        
        # Format timestamp
        timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
        
        # Build the log message
        parts = [
            f"{self.DIM}{timestamp}{self.RESET}",
            f"{color}{record.levelname:8}{self.RESET}",
            f"{self.DIM}[{cid}]{self.RESET}",
            f"{self.BOLD}{record.name}{self.RESET}",
            f"→ {record.getMessage()}"
        ]
        
        message = " ".join(parts)
        
        # Add duration if present
        if hasattr(record, 'duration_ms'):
            message += f" {self.DIM}({record.duration_ms:.2f}ms){self.RESET}"
        
        # Add exception info
        if record.exc_info:
            message += f"\n{self.formatException(record.exc_info)}"
        
        return message


class ContextLogger(logging.LoggerAdapter):
    """
    Logger adapter that automatically includes correlation ID and extra context.
    """
    
    def process(self, msg: str, kwargs: dict) -> tuple:
        # Ensure extra dict exists
        extra = kwargs.get('extra', {})
        extra['correlation_id'] = get_correlation_id()
        kwargs['extra'] = extra
        return msg, kwargs
    
    def with_context(self, **context) -> 'ContextLogger':
        """Create a new logger with additional context."""
        new_extra = {**self.extra, **context}
        return ContextLogger(self.logger, new_extra)


def setup_logging() -> None:
    """
    Configure logging for the application.
    Call this once during application startup.
    """
    settings = get_settings()
    
    # Determine log level from settings
    log_level_str = settings.log_level.upper()
    log_level = getattr(logging, log_level_str, logging.INFO)
    
    # Determine if we're in production (use JSON) or development (use colored)
    is_production = settings.is_production
    
    # Create root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Remove existing handlers
    root_logger.handlers.clear()
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    
    if is_production:
        console_handler.setFormatter(JSONFormatter())
    else:
        console_handler.setFormatter(ColoredConsoleFormatter())
    
    root_logger.addHandler(console_handler)
    
    # File handler with rotation (optional, for persistent logging)
    if settings.enable_file_logging:
        log_dir = Path('logs')
        log_dir.mkdir(exist_ok=True)
        
        # Main log file
        file_handler = logging.handlers.RotatingFileHandler(
            log_dir / 'kanso.log',
            maxBytes=settings.log_max_bytes,
            backupCount=settings.log_backup_count,
            encoding='utf-8'
        )
        file_handler.setLevel(log_level)
        file_handler.setFormatter(JSONFormatter())
        root_logger.addHandler(file_handler)
        
        # Error-only log file
        error_handler = logging.handlers.RotatingFileHandler(
            log_dir / 'kanso-errors.log',
            maxBytes=settings.log_max_bytes,
            backupCount=settings.log_backup_count,
            encoding='utf-8'
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(JSONFormatter())
        root_logger.addHandler(error_handler)
    
    # Configure third-party loggers to be less verbose
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('httpcore').setLevel(logging.WARNING)
    logging.getLogger('uvicorn.access').setLevel(logging.WARNING)
    logging.getLogger('google').setLevel(logging.WARNING)
    
    # Log startup info
    logger = get_logger(__name__)
    logger.info(
        "Logging initialized",
        extra={'extra_data': {
            'level': log_level_str,
            'environment': settings.environment,
            'production_mode': is_production,
            'file_logging': settings.enable_file_logging
        }}
    )


def get_logger(name: str) -> ContextLogger:
    """
    Get a context-aware logger for the given module name.
    
    Usage:
        logger = get_logger(__name__)
        logger.info("Something happened", extra={'extra_data': {'key': 'value'}})
    """
    return ContextLogger(logging.getLogger(name), {})


def log_execution_time(logger: ContextLogger = None, level: int = logging.DEBUG):
    """
    Decorator to log function execution time.
    
    Usage:
        @log_execution_time()
        def my_function():
            ...
    """
    def decorator(func: Callable) -> Callable:
        nonlocal logger
        if logger is None:
            logger = get_logger(func.__module__)
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start = time.perf_counter()
            try:
                result = func(*args, **kwargs)
                duration_ms = (time.perf_counter() - start) * 1000
                record = logging.LogRecord(
                    name=logger.logger.name,
                    level=level,
                    pathname="",
                    lineno=0,
                    msg=f"{func.__name__} completed",
                    args=(),
                    exc_info=None
                )
                record.duration_ms = duration_ms
                record.funcName = func.__name__
                logger.logger.handle(record)
                return result
            except Exception as e:
                duration_ms = (time.perf_counter() - start) * 1000
                logger.error(
                    f"{func.__name__} failed after {duration_ms:.2f}ms: {e}",
                    exc_info=True
                )
                raise
        
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start = time.perf_counter()
            try:
                result = await func(*args, **kwargs)
                duration_ms = (time.perf_counter() - start) * 1000
                record = logging.LogRecord(
                    name=logger.logger.name,
                    level=level,
                    pathname="",
                    lineno=0,
                    msg=f"{func.__name__} completed",
                    args=(),
                    exc_info=None
                )
                record.duration_ms = duration_ms
                record.funcName = func.__name__
                logger.logger.handle(record)
                return result
            except Exception as e:
                duration_ms = (time.perf_counter() - start) * 1000
                logger.error(
                    f"{func.__name__} failed after {duration_ms:.2f}ms: {e}",
                    exc_info=True
                )
                raise
        
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    
    return decorator


class LogContext:
    """
    Context manager for adding temporary context to logs.
    
    Usage:
        with LogContext(user_id="123", action="create_plan"):
            logger.info("Processing request")  # Will include user_id and action
    """
    
    def __init__(self, **context):
        self.context = context
        self.previous_correlation_id = None
    
    def __enter__(self):
        if 'correlation_id' in self.context:
            self.previous_correlation_id = get_correlation_id()
            set_correlation_id(self.context['correlation_id'])
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.previous_correlation_id is not None:
            set_correlation_id(self.previous_correlation_id)
        return False
