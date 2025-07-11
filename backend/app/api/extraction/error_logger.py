"""
Error Logger - Contextual error logging with categorization and recovery tracking
"""

import asyncio
import json
import traceback
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
from enum import Enum
import structlog
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.exceptions import StarboardException

logger = structlog.get_logger(__name__)


class ErrorCategory(str, Enum):
    """Categories for error classification"""
    NETWORK_ERROR = "network_error"
    AUTHENTICATION_ERROR = "authentication_error"
    AUTHORIZATION_ERROR = "authorization_error"
    RATE_LIMIT_ERROR = "rate_limit_error"
    DATA_VALIDATION_ERROR = "data_validation_error"
    DATA_TRANSFORMATION_ERROR = "data_transformation_error"
    EXTRACTION_ERROR = "extraction_error"
    CIRCUIT_BREAKER = "circuit_breaker"
    RETRY_EXHAUSTED = "retry_exhausted"
    TIMEOUT_ERROR = "timeout_error"
    CONFIGURATION_ERROR = "configuration_error"
    SYSTEM_ERROR = "system_error"
    BUSINESS_LOGIC_ERROR = "business_logic_error"
    UNKNOWN_ERROR = "unknown_error"


class ErrorSeverity(str, Enum):
    """Error severity levels"""
    CRITICAL = "critical"  # System cannot function
    ERROR = "error"        # Operation failed
    WARNING = "warning"    # Operation succeeded with issues
    INFO = "info"         # Informational


class ErrorRecoveryAction(str, Enum):
    """Possible recovery actions"""
    RETRY = "retry"
    FALLBACK = "fallback"
    SKIP = "skip"
    ABORT = "abort"
    MANUAL_INTERVENTION = "manual_intervention"
    CIRCUIT_BREAKER_OPEN = "circuit_breaker_open"
    BACKOFF = "backoff"


class ErrorContext(BaseModel):
    """Context information for error debugging"""
    extractor_name: str
    request_id: Optional[str] = None
    source: Optional[str] = None
    target: Optional[str] = None
    operation: Optional[str] = None
    parameters: Dict[str, Any] = Field(default_factory=dict)
    user_agent: Optional[str] = None
    ip_address: Optional[str] = None
    session_id: Optional[str] = None
    correlation_id: Optional[str] = None
    environment: str = "production"
    version: Optional[str] = None
    
    # Request context
    request_headers: Dict[str, str] = Field(default_factory=dict)
    request_body: Optional[str] = None
    response_status: Optional[int] = None
    response_headers: Dict[str, str] = Field(default_factory=dict)
    response_body: Optional[str] = None
    
    # System context
    cpu_usage: Optional[float] = None
    memory_usage: Optional[float] = None
    disk_usage: Optional[float] = None
    active_connections: Optional[int] = None
    
    # Timing context
    request_start_time: Optional[datetime] = None
    error_time: datetime = Field(default_factory=datetime.utcnow)
    processing_duration_ms: Optional[float] = None
    
    # Debug context
    stack_trace: Optional[str] = None
    local_variables: Dict[str, Any] = Field(default_factory=dict)
    thread_id: Optional[str] = None
    process_id: Optional[int] = None


class ErrorRecord(BaseModel):
    """Complete error record for logging and analysis"""
    id: str = Field(..., description="Unique error identifier")
    category: ErrorCategory
    severity: ErrorSeverity
    message: str
    error_type: str
    error_code: Optional[str] = None
    
    # Context
    context: ErrorContext
    
    # Recovery information
    recovery_action: Optional[ErrorRecoveryAction] = None
    recovery_successful: Optional[bool] = None
    recovery_attempts: int = 0
    recovery_details: Dict[str, Any] = Field(default_factory=dict)
    
    # Metadata
    tags: List[str] = Field(default_factory=list)
    custom_data: Dict[str, Any] = Field(default_factory=dict)
    
    # Timing
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    resolution_time: Optional[datetime] = None
    ttl_hours: int = 168  # 7 days default retention


class ErrorPattern(BaseModel):
    """Pattern for error analysis and alerting"""
    pattern_id: str
    name: str
    description: str
    category: ErrorCategory
    conditions: Dict[str, Any] = Field(default_factory=dict)
    threshold_count: int = 5
    threshold_time_window_minutes: int = 60
    escalation_severity: ErrorSeverity = ErrorSeverity.ERROR
    alert_enabled: bool = True
    auto_recovery_enabled: bool = False
    recovery_action: Optional[ErrorRecoveryAction] = None


class ErrorStats(BaseModel):
    """Error statistics and metrics"""
    total_errors: int = 0
    errors_by_category: Dict[ErrorCategory, int] = Field(default_factory=dict)
    errors_by_severity: Dict[ErrorSeverity, int] = Field(default_factory=dict)
    errors_by_hour: Dict[str, int] = Field(default_factory=dict)
    top_error_types: List[Dict[str, Any]] = Field(default_factory=list)
    recovery_success_rate: float = 0.0
    average_resolution_time_minutes: float = 0.0
    most_frequent_patterns: List[str] = Field(default_factory=list)
    last_updated: datetime = Field(default_factory=datetime.utcnow)


class ErrorLogger:
    """Contextual error logger with categorization and recovery tracking"""
    
    def __init__(self, extractor_name: str):
        self.extractor_name = extractor_name
        self.error_records: List[ErrorRecord] = []
        self.error_patterns: Dict[str, ErrorPattern] = {}
        self.stats = ErrorStats()
        
        # Pattern matching cache
        self.pattern_cache: Dict[str, List[str]] = {}
        
        # Load default error patterns
        self._load_default_patterns()
        
        logger.info("Error logger initialized", extractor_name=extractor_name)
    
    def _load_default_patterns(self):
        """Load default error patterns for common issues"""
        patterns = [
            ErrorPattern(
                pattern_id="network_timeout_burst",
                name="Network Timeout Burst",
                description="Multiple network timeouts in short period",
                category=ErrorCategory.NETWORK_ERROR,
                conditions={"error_type": "TimeoutError", "count": 5, "window_minutes": 10},
                threshold_count=5,
                threshold_time_window_minutes=10,
                escalation_severity=ErrorSeverity.ERROR,
                auto_recovery_enabled=True,
                recovery_action=ErrorRecoveryAction.BACKOFF
            ),
            
            ErrorPattern(
                pattern_id="rate_limit_exceeded",
                name="Rate Limit Exceeded",
                description="Rate limiting errors detected",
                category=ErrorCategory.RATE_LIMIT_ERROR,
                conditions={"response_status": 429},
                threshold_count=3,
                threshold_time_window_minutes=5,
                escalation_severity=ErrorSeverity.WARNING,
                auto_recovery_enabled=True,
                recovery_action=ErrorRecoveryAction.BACKOFF
            ),
            
            ErrorPattern(
                pattern_id="authentication_failure_pattern",
                name="Authentication Failure Pattern",
                description="Repeated authentication failures",
                category=ErrorCategory.AUTHENTICATION_ERROR,
                conditions={"response_status": [401, 403]},
                threshold_count=3,
                threshold_time_window_minutes=30,
                escalation_severity=ErrorSeverity.CRITICAL,
                auto_recovery_enabled=False,
                recovery_action=ErrorRecoveryAction.MANUAL_INTERVENTION
            ),
            
            ErrorPattern(
                pattern_id="data_validation_spike",
                name="Data Validation Error Spike",
                description="High rate of data validation errors",
                category=ErrorCategory.DATA_VALIDATION_ERROR,
                conditions={"category": "data_validation_error"},
                threshold_count=20,
                threshold_time_window_minutes=15,
                escalation_severity=ErrorSeverity.ERROR,
                auto_recovery_enabled=False
            ),
            
            ErrorPattern(
                pattern_id="circuit_breaker_trips",
                name="Circuit Breaker Frequent Trips",
                description="Circuit breaker opening frequently",
                category=ErrorCategory.CIRCUIT_BREAKER,
                conditions={"category": "circuit_breaker"},
                threshold_count=3,
                threshold_time_window_minutes=60,
                escalation_severity=ErrorSeverity.CRITICAL,
                auto_recovery_enabled=False,
                recovery_action=ErrorRecoveryAction.MANUAL_INTERVENTION
            )
        ]
        
        for pattern in patterns:
            self.error_patterns[pattern.pattern_id] = pattern
    
    async def log_error(
        self,
        error_message: str,
        category: Union[ErrorCategory, str] = ErrorCategory.UNKNOWN_ERROR,
        severity: ErrorSeverity = ErrorSeverity.ERROR,
        error_type: Optional[str] = None,
        error_code: Optional[str] = None,
        request_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
        custom_data: Optional[Dict[str, Any]] = None,
        exception: Optional[Exception] = None
    ) -> str:
        """
        Log an error with full context
        
        Args:
            error_message: Human-readable error message
            category: Error category
            severity: Error severity level
            error_type: Type of error (exception class name)
            error_code: Optional error code
            request_id: Associated request ID
            context: Additional context data
            tags: List of tags for categorization
            custom_data: Custom metadata
            exception: Original exception object
            
        Returns:
            Error record ID
        """
        try:
            # Convert string category to enum
            if isinstance(category, str):
                try:
                    category = ErrorCategory(category)
                except ValueError:
                    category = ErrorCategory.UNKNOWN_ERROR
            
            # Generate unique error ID
            error_id = f"err_{datetime.utcnow().strftime('%Y%m%d_%H%M%S_%f')}"
            
            # Build error context
            error_context = await self._build_error_context(
                request_id=request_id,
                context_data=context or {},
                exception=exception
            )
            
            # Determine error type from exception
            if not error_type and exception:
                error_type = type(exception).__name__
            
            # Create error record
            error_record = ErrorRecord(
                id=error_id,
                category=category,
                severity=severity,
                message=error_message,
                error_type=error_type or "Unknown",
                error_code=error_code,
                context=error_context,
                tags=tags or [],
                custom_data=custom_data or {}
            )
            
            # Store error record
            self.error_records.append(error_record)
            
            # Check for error patterns
            await self._check_error_patterns(error_record)
            
            # Update statistics
            await self._update_stats(error_record)
            
            # Log to structured logger
            await self._log_to_structured_logger(error_record)
            
            # Clean up old errors
            self._cleanup_old_errors()
            
            logger.info("Error recorded", 
                       error_id=error_id,
                       category=category.value,
                       severity=severity.value,
                       extractor=self.extractor_name)
            
            return error_id
            
        except Exception as e:
            # Fallback logging if error logging fails
            logger.error("Failed to log error", 
                        original_error=error_message,
                        logging_error=str(e),
                        extractor=self.extractor_name)
            return "logging_failed"
    
    async def _build_error_context(
        self,
        request_id: Optional[str] = None,
        context_data: Dict[str, Any] = None,
        exception: Optional[Exception] = None
    ) -> ErrorContext:
        """Build comprehensive error context"""
        context_data = context_data or {}
        
        # Capture stack trace
        stack_trace = None
        if exception:
            stack_trace = traceback.format_exception(
                type(exception), exception, exception.__traceback__
            )
            stack_trace = ''.join(stack_trace)
        
        # Get system metrics
        cpu_usage, memory_usage = await self._get_system_metrics()
        
        # Build context
        context = ErrorContext(
            extractor_name=self.extractor_name,
            request_id=request_id,
            source=context_data.get("source"),
            target=context_data.get("target"),
            operation=context_data.get("operation"),
            parameters=context_data.get("parameters", {}),
            environment=settings.get("ENVIRONMENT", "production"),
            cpu_usage=cpu_usage,
            memory_usage=memory_usage,
            stack_trace=stack_trace,
            thread_id=str(asyncio.current_task().get_name()) if asyncio.current_task() else None
        )
        
        # Add HTTP context if available
        if "request_headers" in context_data:
            context.request_headers = context_data["request_headers"]
        if "response_status" in context_data:
            context.response_status = context_data["response_status"]
        if "response_headers" in context_data:
            context.response_headers = context_data["response_headers"]
        
        # Add timing context
        if "request_start_time" in context_data:
            context.request_start_time = context_data["request_start_time"]
            if context.request_start_time:
                duration = (datetime.utcnow() - context.request_start_time).total_seconds() * 1000
                context.processing_duration_ms = duration
        
        return context
    
    async def _get_system_metrics(self) -> tuple[Optional[float], Optional[float]]:
        """Get current system metrics"""
        try:
            import psutil
            cpu_usage = psutil.cpu_percent(interval=0.1) / 100.0
            memory_usage = psutil.virtual_memory().percent / 100.0
            return cpu_usage, memory_usage
        except ImportError:
            return None, None
    
    async def _check_error_patterns(self, error_record: ErrorRecord):
        """Check if error matches any defined patterns"""
        for pattern_id, pattern in self.error_patterns.items():
            if await self._matches_pattern(error_record, pattern):
                await self._handle_pattern_match(pattern_id, pattern, error_record)
    
    async def _matches_pattern(self, error_record: ErrorRecord, pattern: ErrorPattern) -> bool:
        """Check if error record matches a pattern"""
        # Check category match
        if pattern.category != error_record.category:
            return False
        
        # Check specific conditions
        conditions = pattern.conditions
        
        # Check error type
        if "error_type" in conditions:
            if error_record.error_type != conditions["error_type"]:
                return False
        
        # Check response status
        if "response_status" in conditions:
            expected_status = conditions["response_status"]
            actual_status = error_record.context.response_status
            
            if isinstance(expected_status, list):
                if actual_status not in expected_status:
                    return False
            else:
                if actual_status != expected_status:
                    return False
        
        # Check time window and count
        if "count" in conditions and "window_minutes" in conditions:
            window_start = datetime.utcnow() - timedelta(minutes=conditions["window_minutes"])
            recent_errors = [
                err for err in self.error_records
                if (err.timestamp >= window_start and 
                    err.category == pattern.category and
                    self._error_matches_basic_conditions(err, conditions))
            ]
            
            if len(recent_errors) < conditions["count"]:
                return False
        
        return True
    
    def _error_matches_basic_conditions(self, error_record: ErrorRecord, conditions: Dict[str, Any]) -> bool:
        """Check if error matches basic pattern conditions"""
        if "error_type" in conditions:
            if error_record.error_type != conditions["error_type"]:
                return False
        
        if "response_status" in conditions:
            expected_status = conditions["response_status"]
            actual_status = error_record.context.response_status
            
            if isinstance(expected_status, list):
                if actual_status not in expected_status:
                    return False
            else:
                if actual_status != expected_status:
                    return False
        
        return True
    
    async def _handle_pattern_match(
        self,
        pattern_id: str,
        pattern: ErrorPattern,
        error_record: ErrorRecord
    ):
        """Handle when an error pattern is matched"""
        logger.warning("Error pattern matched", 
                      pattern_id=pattern_id,
                      pattern_name=pattern.name,
                      error_id=error_record.id,
                      extractor=self.extractor_name)
        
        # Add pattern tag to error
        error_record.tags.append(f"pattern:{pattern_id}")
        
        # Check if auto-recovery is enabled
        if pattern.auto_recovery_enabled and pattern.recovery_action:
            await self._attempt_auto_recovery(pattern, error_record)
        
        # Send alert if enabled
        if pattern.alert_enabled:
            await self._send_pattern_alert(pattern, error_record)
    
    async def _attempt_auto_recovery(self, pattern: ErrorPattern, error_record: ErrorRecord):
        """Attempt automatic recovery based on pattern"""
        try:
            recovery_action = pattern.recovery_action
            
            logger.info("Attempting auto-recovery", 
                       pattern_id=pattern.pattern_id,
                       recovery_action=recovery_action.value,
                       error_id=error_record.id)
            
            if recovery_action == ErrorRecoveryAction.BACKOFF:
                # Implement backoff logic
                await self._implement_backoff_recovery(error_record)
            
            elif recovery_action == ErrorRecoveryAction.CIRCUIT_BREAKER_OPEN:
                # Trigger circuit breaker
                await self._trigger_circuit_breaker(error_record)
            
            # Update recovery information
            error_record.recovery_action = recovery_action
            error_record.recovery_attempts += 1
            error_record.recovery_details["auto_recovery_attempted"] = True
            error_record.recovery_details["recovery_time"] = datetime.utcnow().isoformat()
            
        except Exception as e:
            logger.error("Auto-recovery failed", 
                        pattern_id=pattern.pattern_id,
                        error=str(e))
            
            error_record.recovery_successful = False
            error_record.recovery_details["auto_recovery_error"] = str(e)
    
    async def _implement_backoff_recovery(self, error_record: ErrorRecord):
        """Implement backoff recovery strategy"""
        # This would integrate with the retry handler to increase backoff times
        logger.info("Implementing backoff recovery", error_id=error_record.id)
        error_record.recovery_details["backoff_applied"] = True
    
    async def _trigger_circuit_breaker(self, error_record: ErrorRecord):
        """Trigger circuit breaker opening"""
        # This would integrate with the circuit breaker to force it open
        logger.warning("Triggering circuit breaker", error_id=error_record.id)
        error_record.recovery_details["circuit_breaker_triggered"] = True
    
    async def _send_pattern_alert(self, pattern: ErrorPattern, error_record: ErrorRecord):
        """Send alert for pattern match"""
        alert_data = {
            "pattern_id": pattern.pattern_id,
            "pattern_name": pattern.name,
            "severity": pattern.escalation_severity.value,
            "error_id": error_record.id,
            "extractor": self.extractor_name,
            "timestamp": datetime.utcnow().isoformat(),
            "description": pattern.description
        }
        
        # Log alert (in production, this would send to alerting system)
        logger.warning("Error pattern alert", **alert_data)
    
    async def _update_stats(self, error_record: ErrorRecord):
        """Update error statistics"""
        self.stats.total_errors += 1
        
        # Update category stats
        category = error_record.category
        if category not in self.stats.errors_by_category:
            self.stats.errors_by_category[category] = 0
        self.stats.errors_by_category[category] += 1
        
        # Update severity stats
        severity = error_record.severity
        if severity not in self.stats.errors_by_severity:
            self.stats.errors_by_severity[severity] = 0
        self.stats.errors_by_severity[severity] += 1
        
        # Update hourly stats
        hour_key = error_record.timestamp.strftime("%Y-%m-%d %H")
        if hour_key not in self.stats.errors_by_hour:
            self.stats.errors_by_hour[hour_key] = 0
        self.stats.errors_by_hour[hour_key] += 1
        
        # Update recovery success rate
        total_recovery_attempts = sum(
            1 for err in self.error_records 
            if err.recovery_attempts > 0
        )
        successful_recoveries = sum(
            1 for err in self.error_records 
            if err.recovery_successful is True
        )
        
        if total_recovery_attempts > 0:
            self.stats.recovery_success_rate = successful_recoveries / total_recovery_attempts
        
        self.stats.last_updated = datetime.utcnow()
    
    async def _log_to_structured_logger(self, error_record: ErrorRecord):
        """Log to structured logging system"""
        log_data = {
            "error_id": error_record.id,
            "category": error_record.category.value,
            "severity": error_record.severity.value,
            "message": error_record.message,
            "error_type": error_record.error_type,
            "extractor": self.extractor_name,
            "request_id": error_record.context.request_id,
            "source": error_record.context.source,
            "target": error_record.context.target,
            "tags": error_record.tags
        }
        
        if error_record.severity == ErrorSeverity.CRITICAL:
            logger.critical("Critical error logged", **log_data)
        elif error_record.severity == ErrorSeverity.ERROR:
            logger.error("Error logged", **log_data)
        elif error_record.severity == ErrorSeverity.WARNING:
            logger.warning("Warning logged", **log_data)
        else:
            logger.info("Info logged", **log_data)
    
    def _cleanup_old_errors(self):
        """Clean up old error records based on TTL"""
        cutoff_time = datetime.utcnow() - timedelta(hours=168)  # 7 days default
        
        before_count = len(self.error_records)
        self.error_records = [
            err for err in self.error_records
            if err.timestamp > cutoff_time
        ]
        after_count = len(self.error_records)
        
        if before_count != after_count:
            logger.debug("Cleaned up old errors", 
                        removed=before_count - after_count,
                        remaining=after_count)
    
    async def mark_error_resolved(
        self,
        error_id: str,
        resolution_notes: Optional[str] = None,
        recovery_successful: bool = True
    ):
        """Mark an error as resolved"""
        for error_record in self.error_records:
            if error_record.id == error_id:
                error_record.resolution_time = datetime.utcnow()
                error_record.recovery_successful = recovery_successful
                
                if resolution_notes:
                    error_record.recovery_details["resolution_notes"] = resolution_notes
                
                logger.info("Error marked as resolved", 
                           error_id=error_id,
                           recovery_successful=recovery_successful)
                break
    
    def get_error_by_id(self, error_id: str) -> Optional[ErrorRecord]:
        """Get error record by ID"""
        for error_record in self.error_records:
            if error_record.id == error_id:
                return error_record
        return None
    
    def get_recent_errors(
        self,
        hours: int = 24,
        category: Optional[ErrorCategory] = None,
        severity: Optional[ErrorSeverity] = None,
        limit: int = 100
    ) -> List[ErrorRecord]:
        """Get recent errors with optional filtering"""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        
        filtered_errors = [
            err for err in self.error_records
            if err.timestamp > cutoff_time
        ]
        
        if category:
            filtered_errors = [err for err in filtered_errors if err.category == category]
        
        if severity:
            filtered_errors = [err for err in filtered_errors if err.severity == severity]
        
        # Sort by timestamp (newest first)
        filtered_errors.sort(key=lambda x: x.timestamp, reverse=True)
        
        return filtered_errors[:limit]
    
    def get_error_stats(self) -> ErrorStats:
        """Get current error statistics"""
        return self.stats
    
    def get_error_patterns_status(self) -> Dict[str, Any]:
        """Get status of error patterns"""
        pattern_status = {}
        
        for pattern_id, pattern in self.error_patterns.items():
            # Count recent matches
            window_start = datetime.utcnow() - timedelta(minutes=pattern.threshold_time_window_minutes)
            recent_matches = len([
                err for err in self.error_records
                if (err.timestamp >= window_start and 
                    f"pattern:{pattern_id}" in err.tags)
            ])
            
            pattern_status[pattern_id] = {
                "name": pattern.name,
                "category": pattern.category.value,
                "threshold_count": pattern.threshold_count,
                "recent_matches": recent_matches,
                "threshold_reached": recent_matches >= pattern.threshold_count,
                "auto_recovery_enabled": pattern.auto_recovery_enabled,
                "alert_enabled": pattern.alert_enabled
            }
        
        return pattern_status
    
    async def export_errors(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        format: str = "json"
    ) -> Union[str, Dict[str, Any]]:
        """Export errors for analysis"""
        if not start_time:
            start_time = datetime.utcnow() - timedelta(days=7)
        if not end_time:
            end_time = datetime.utcnow()
        
        filtered_errors = [
            err for err in self.error_records
            if start_time <= err.timestamp <= end_time
        ]
        
        export_data = {
            "export_timestamp": datetime.utcnow().isoformat(),
            "extractor": self.extractor_name,
            "period": {
                "start": start_time.isoformat(),
                "end": end_time.isoformat()
            },
            "total_errors": len(filtered_errors),
            "errors": [err.dict() for err in filtered_errors],
            "statistics": self.stats.dict()
        }
        
        if format == "json":
            return json.dumps(export_data, indent=2, default=str)
        else:
            return export_data
    
    async def close(self):
        """Close error logger and clean up resources"""
        logger.info("Closing error logger", 
                   extractor=self.extractor_name,
                   total_errors_logged=len(self.error_records))
        
        # Clear error records to free memory
        self.error_records.clear()
        self.pattern_cache.clear() 