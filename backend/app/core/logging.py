import logging
import sys
from typing import Any
import structlog
from app.core.config import settings

def setup_logging() -> None:
    """Configure structured logging for the application."""
    
    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, settings.LOG_LEVEL.upper()),
    )
    
    # Configure structlog
    structlog.configure(
        processors=[
            # Add timestamp
            structlog.processors.TimeStamper(fmt="ISO"),
            # Add log level
            structlog.processors.add_log_level,
            # Add caller info
            structlog.processors.CallsiteParameterAdder(
                parameters=[structlog.processors.CallsiteParameter.PATHNAME,
                           structlog.processors.CallsiteParameter.FUNC_NAME,
                           structlog.processors.CallsiteParameter.LINENO]
            ),
            # JSON formatting for structured logs
            structlog.processors.JSONRenderer()
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

def get_logger(name: str) -> Any:
    """Get a configured logger instance."""
    return structlog.get_logger(name) 