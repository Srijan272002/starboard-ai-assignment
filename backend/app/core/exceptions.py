from typing import Any, Dict, Optional
from fastapi import HTTPException, status

class StarboardException(Exception):
    """Base exception for Starboard application."""
    
    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        super().__init__(self.message)

class APIException(StarboardException):
    """Exception for API-related errors."""
    pass

class DatabaseException(StarboardException):
    """Exception for database-related errors."""
    pass

class ValidationException(StarboardException):
    """Exception for data validation errors."""
    pass

class RateLimitException(StarboardException):
    """Exception for rate limiting errors."""
    pass

class ConfigurationException(StarboardException):
    """Exception for configuration-related errors."""
    pass

# HTTP Exception handlers
def create_http_exception(
    status_code: int,
    message: str,
    error_code: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None
) -> HTTPException:
    """Create an HTTP exception with structured error response."""
    
    error_detail = {
        "message": message,
        "error_code": error_code,
        "details": details or {}
    }
    
    return HTTPException(
        status_code=status_code,
        detail=error_detail
    )

# Common HTTP exceptions
def not_found_exception(message: str = "Resource not found") -> HTTPException:
    return create_http_exception(
        status_code=status.HTTP_404_NOT_FOUND,
        message=message,
        error_code="RESOURCE_NOT_FOUND"
    )

def bad_request_exception(message: str = "Bad request") -> HTTPException:
    return create_http_exception(
        status_code=status.HTTP_400_BAD_REQUEST,
        message=message,
        error_code="BAD_REQUEST"
    )

def internal_server_exception(message: str = "Internal server error") -> HTTPException:
    return create_http_exception(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        message=message,
        error_code="INTERNAL_SERVER_ERROR"
    ) 