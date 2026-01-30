"""
FastAPI middleware for request/response logging and monitoring.
"""

import time
from typing import Callable
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from fastapi import FastAPI

from .logging_config import get_logger, set_correlation_id, get_correlation_id

logger = get_logger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware that logs all HTTP requests with timing and correlation IDs.
    
    Features:
    - Generates/propagates correlation IDs (X-Correlation-ID header)
    - Logs request start with method, path, client IP
    - Logs request completion with status code and duration
    - Adds correlation ID to response headers for tracing
    """
    
    # Paths to exclude from detailed logging (health checks, etc.)
    EXCLUDED_PATHS = {'/health', '/favicon.ico', '/docs', '/redoc', '/openapi.json'}
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Extract or generate correlation ID
        correlation_id = request.headers.get('X-Correlation-ID')
        correlation_id = set_correlation_id(correlation_id)
        
        # Check if this path should be logged
        should_log = request.url.path not in self.EXCLUDED_PATHS
        
        # Get client info
        client_ip = request.client.host if request.client else 'unknown'
        method = request.method
        path = request.url.path
        query = str(request.query_params) if request.query_params else ''
        
        # Log request start
        if should_log:
            logger.info(
                f"→ {method} {path}",
                extra={'extra_data': {
                    'event': 'request_start',
                    'method': method,
                    'path': path,
                    'query': query,
                    'client_ip': client_ip,
                    'user_agent': request.headers.get('user-agent', 'unknown')[:100]
                }}
            )
        
        # Process request and measure time
        start_time = time.perf_counter()
        
        try:
            response = await call_next(request)
            duration_ms = (time.perf_counter() - start_time) * 1000
            
            # Log request completion
            if should_log:
                log_level = 'info' if response.status_code < 400 else 'warning' if response.status_code < 500 else 'error'
                getattr(logger, log_level)(
                    f"← {method} {path} {response.status_code} ({duration_ms:.2f}ms)",
                    extra={'extra_data': {
                        'event': 'request_complete',
                        'method': method,
                        'path': path,
                        'status_code': response.status_code,
                        'duration_ms': round(duration_ms, 2),
                        'client_ip': client_ip
                    }}
                )
            
            # Add correlation ID to response headers
            response.headers['X-Correlation-ID'] = correlation_id
            response.headers['X-Response-Time'] = f"{duration_ms:.2f}ms"
            
            return response
            
        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000
            
            logger.error(
                f"✗ {method} {path} failed ({duration_ms:.2f}ms): {str(e)}",
                exc_info=True,
                extra={'extra_data': {
                    'event': 'request_error',
                    'method': method,
                    'path': path,
                    'duration_ms': round(duration_ms, 2),
                    'error': str(e),
                    'client_ip': client_ip
                }}
            )
            raise


class WebSocketLoggingMiddleware:
    """
    Helper class for logging WebSocket connections and messages.
    Not a true middleware - use the methods directly in WebSocket handlers.
    """
    
    def __init__(self, client_id: str):
        self.client_id = client_id
        self.connection_start = time.perf_counter()
        self.message_count = 0
        self.logger = get_logger(f"{__name__}.ws.{client_id}")
    
    def log_connect(self):
        """Log WebSocket connection."""
        set_correlation_id(self.client_id[:8])
        self.logger.info(
            f"WebSocket connected",
            extra={'extra_data': {
                'event': 'ws_connect',
                'client_id': self.client_id
            }}
        )
    
    def log_message(self, action: str, data: dict = None):
        """Log incoming WebSocket message."""
        self.message_count += 1
        self.logger.debug(
            f"WebSocket message: {action}",
            extra={'extra_data': {
                'event': 'ws_message',
                'client_id': self.client_id,
                'action': action,
                'message_number': self.message_count
            }}
        )
    
    def log_response(self, message_type: str, success: bool = True):
        """Log outgoing WebSocket response."""
        log_method = self.logger.debug if success else self.logger.warning
        log_method(
            f"WebSocket response: {message_type}",
            extra={'extra_data': {
                'event': 'ws_response',
                'client_id': self.client_id,
                'message_type': message_type,
                'success': success
            }}
        )
    
    def log_disconnect(self, reason: str = "client disconnected"):
        """Log WebSocket disconnection."""
        duration_s = time.perf_counter() - self.connection_start
        self.logger.info(
            f"WebSocket disconnected: {reason}",
            extra={'extra_data': {
                'event': 'ws_disconnect',
                'client_id': self.client_id,
                'reason': reason,
                'duration_seconds': round(duration_s, 2),
                'total_messages': self.message_count
            }}
        )


def add_logging_middleware(app: FastAPI) -> None:
    """Add all logging middleware to the FastAPI app."""
    app.add_middleware(RequestLoggingMiddleware)
