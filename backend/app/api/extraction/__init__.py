"""
Data Extraction Framework Package

This package contains the Phase 3.1 Core Extraction Framework components for 
intelligent data extraction from county APIs with robust error handling, 
retry logic, and batch processing.
"""

from .base_extractor import (
    BaseExtractor,
    ExtractionRequest,
    ExtractionResult,
    ExtractionStatus,
    ExtractionPriority,
    ExtractionMetrics
)
from .retry_handler import RetryHandler, RetryConfig, RetryStrategy
from .circuit_breaker import CircuitBreaker, CircuitBreakerConfig, CircuitBreakerState
from .batch_processor import BatchProcessor, BatchProcessorConfig
from .validation_engine import ValidationEngine, ValidationRule as ExtractionValidationRule
from .error_logger import (
    ErrorLogger,
    ErrorCategory,
    ErrorContext,
    ErrorSeverity,
    ErrorRecoveryAction,
    ErrorRecord,
    ErrorPattern,
    ErrorStats
)

__all__ = [
    "BaseExtractor",
    "ExtractionRequest", 
    "ExtractionResult",
    "ExtractionStatus",
    "ExtractionPriority",
    "ExtractionMetrics",
    "RetryHandler",
    "RetryConfig",
    "RetryStrategy",
    "CircuitBreaker",
    "CircuitBreakerConfig", 
    "CircuitBreakerState",
    "BatchProcessor",
    "BatchProcessorConfig",
    "ValidationEngine",
    "ExtractionValidationRule",
    "ErrorLogger",
    "ErrorCategory",
    "ErrorContext",
    "ErrorSeverity",
    "ErrorRecoveryAction",
    "ErrorRecord",
    "ErrorPattern",
    "ErrorStats"
] 