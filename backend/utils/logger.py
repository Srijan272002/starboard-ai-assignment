import logging
import sys
import json
import traceback
from pathlib import Path
from datetime import datetime
from logging.handlers import RotatingFileHandler
from typing import Dict, Optional, Any
from functools import wraps
from backend.config.settings import get_settings

settings = get_settings()

class JsonFormatter(logging.Formatter):
    """
    Formats log records as JSON
    """
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            'timestamp': datetime.fromtimestamp(record.created).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno
        }
        
        # Add exception info if present
        if record.exc_info:
            log_data['exception'] = {
                'type': record.exc_info[0].__name__,
                'message': str(record.exc_info[1]),
                'traceback': traceback.format_exception(*record.exc_info)
            }
            
        # Add extra fields if present
        if hasattr(record, 'extra_data'):
            log_data['extra'] = record.extra_data
            
        return json.dumps(log_data)

class ErrorLogger:
    """
    Enhanced error logging with context and tracking
    """
    def __init__(self, logger: logging.Logger):
        self.logger = logger
        self.error_counts: Dict[str, int] = {}
        
    def log_error(
        self,
        error: Exception,
        context: Optional[Dict[str, Any]] = None,
        level: int = logging.ERROR
    ) -> None:
        """
        Logs an error with context and updates error counts
        """
        error_type = type(error).__name__
        
        # Update error counts
        self.error_counts[error_type] = self.error_counts.get(error_type, 0) + 1
        
        # Prepare extra data
        extra_data = {
            'error_type': error_type,
            'error_count': self.error_counts[error_type]
        }
        
        if context:
            extra_data['context'] = context
            
        # Create log record
        self.logger.log(
            level,
            str(error),
            exc_info=True,
            extra={'extra_data': extra_data}
        )
        
    def get_error_summary(self) -> Dict[str, int]:
        """
        Returns summary of error counts by type
        """
        return dict(self.error_counts)

def setup_logger(name: str) -> logging.Logger:
    """
    Set up logger with both file and console handlers
    """
    logger = logging.getLogger(name)
    logger.setLevel(settings.LOG_LEVEL)
    
    # Clear any existing handlers
    logger.handlers = []

    # Create logs directory if it doesn't exist
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    # File handler with rotation (JSON format)
    json_handler = RotatingFileHandler(
        log_dir / f"{name}.json",
        maxBytes=10_000_000,  # 10MB
        backupCount=5
    )
    json_handler.setFormatter(JsonFormatter())
    logger.addHandler(json_handler)

    # Text file handler with rotation
    text_handler = RotatingFileHandler(
        log_dir / f"{name}.log",
        maxBytes=10_000_000,  # 10MB
        backupCount=5
    )
    text_handler.setFormatter(logging.Formatter(settings.LOG_FORMAT))
    logger.addHandler(text_handler)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(logging.Formatter(settings.LOG_FORMAT))
    logger.addHandler(console_handler)

    return logger

def log_execution_time(logger: logging.Logger):
    """
    Decorator to log function execution time
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = datetime.now()
            try:
                result = func(*args, **kwargs)
                end_time = datetime.now()
                duration = (end_time - start_time).total_seconds()
                
                logger.debug(
                    f"Function {func.__name__} executed in {duration:.2f} seconds",
                    extra={
                        'extra_data': {
                            'function': func.__name__,
                            'duration': duration,
                            'success': True
                        }
                    }
                )
                return result
                
            except Exception as e:
                end_time = datetime.now()
                duration = (end_time - start_time).total_seconds()
                
                logger.error(
                    f"Error in {func.__name__}: {str(e)}",
                    exc_info=True,
                    extra={
                        'extra_data': {
                            'function': func.__name__,
                            'duration': duration,
                            'success': False
                        }
                    }
                )
                raise
                
        return wrapper
    return decorator

def log_data_operation(logger: logging.Logger, operation: str):
    """
    Decorator to log data operations with context
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                result = func(*args, **kwargs)
                
                # Log success
                logger.info(
                    f"{operation} completed successfully",
                    extra={
                        'extra_data': {
                            'operation': operation,
                            'function': func.__name__,
                            'args_count': len(args),
                            'kwargs_count': len(kwargs),
                            'success': True
                        }
                    }
                )
                
                return result
                
            except Exception as e:
                # Log failure
                logger.error(
                    f"{operation} failed: {str(e)}",
                    exc_info=True,
                    extra={
                        'extra_data': {
                            'operation': operation,
                            'function': func.__name__,
                            'args_count': len(args),
                            'kwargs_count': len(kwargs),
                            'success': False
                        }
                    }
                )
                raise
                
        return wrapper
    return decorator

# Create error loggers for different components
validation_error_logger = ErrorLogger(setup_logger("validation_errors"))
transform_error_logger = ErrorLogger(setup_logger("transform_errors"))
quality_error_logger = ErrorLogger(setup_logger("quality_errors"))
outlier_error_logger = ErrorLogger(setup_logger("outlier_errors")) 