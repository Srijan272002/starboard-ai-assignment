"""
Base Extraction System - Core framework for data extraction
"""

import asyncio
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, List, Optional, Any, AsyncGenerator, Union
from enum import Enum
import structlog
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.exceptions import StarboardException

logger = structlog.get_logger(__name__)


class ExtractionStatus(str, Enum):
    """Status of extraction operation"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRYING = "retrying"
    CIRCUIT_OPEN = "circuit_open"


class ExtractionPriority(str, Enum):
    """Priority levels for extraction requests"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class ExtractionRequest(BaseModel):
    """Request for data extraction"""
    id: str = Field(..., description="Unique request identifier")
    source: str = Field(..., description="Data source identifier")
    target: str = Field(..., description="Target dataset or endpoint")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Extraction parameters")
    priority: ExtractionPriority = Field(default=ExtractionPriority.NORMAL)
    retry_config: Optional[Dict[str, Any]] = Field(default=None, description="Custom retry configuration")
    validation_rules: List[str] = Field(default_factory=list, description="Validation rules to apply")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    timeout_seconds: Optional[int] = Field(default=None, description="Request timeout")


class ExtractionResult(BaseModel):
    """Result of extraction operation"""
    request_id: str
    status: ExtractionStatus
    data: List[Dict[str, Any]] = Field(default_factory=list)
    total_records: int = 0
    processed_records: int = 0
    failed_records: int = 0
    validation_results: Dict[str, Any] = Field(default_factory=dict)
    error_details: Optional[Dict[str, Any]] = None
    retry_count: int = 0
    processing_time_seconds: float = 0.0
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ExtractionMetrics(BaseModel):
    """Metrics for extraction operations"""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    retry_attempts: int = 0
    average_processing_time: float = 0.0
    total_records_extracted: int = 0
    last_extraction_time: Optional[datetime] = None
    circuit_breaker_trips: int = 0
    validation_failures: int = 0


class BaseExtractor(ABC):
    """Base class for data extraction systems"""
    
    def __init__(self, extractor_name: str):
        self.extractor_name = extractor_name
        self.metrics = ExtractionMetrics()
        self.active_extractions: Dict[str, ExtractionResult] = {}
        self._shutdown_event = asyncio.Event()
        
        # Import components
        from .retry_handler import RetryHandler
        from .circuit_breaker import CircuitBreaker
        from .validation_engine import ValidationEngine
        from .error_logger import ErrorLogger
        
        # Initialize components
        self.retry_handler = RetryHandler()
        self.circuit_breaker = CircuitBreaker(f"{extractor_name}_circuit")
        self.validation_engine = ValidationEngine()
        self.error_logger = ErrorLogger(extractor_name)
        
        logger.info("Base extractor initialized", extractor_name=extractor_name)
    
    @abstractmethod
    async def _extract_data(
        self,
        request: ExtractionRequest
    ) -> List[Dict[str, Any]]:
        """
        Extract data from the source - implemented by subclasses
        
        Args:
            request: Extraction request
            
        Returns:
            List of extracted records
        """
        pass
    
    @abstractmethod
    async def _validate_source_connection(self) -> bool:
        """
        Validate connection to the data source
        
        Returns:
            True if connection is valid
        """
        pass
    
    async def extract(
        self,
        request: ExtractionRequest
    ) -> ExtractionResult:
        """
        Main extraction method with full framework support
        
        Args:
            request: Extraction request
            
        Returns:
            Extraction result
        """
        result = ExtractionResult(
            request_id=request.id,
            status=ExtractionStatus.PENDING,
            started_at=datetime.utcnow()
        )
        
        # Store active extraction
        self.active_extractions[request.id] = result
        
        try:
            logger.info("Starting extraction", 
                       request_id=request.id,
                       source=request.source,
                       target=request.target)
            
            # Check circuit breaker
            if not await self.circuit_breaker.can_execute():
                result.status = ExtractionStatus.CIRCUIT_OPEN
                result.error_details = {
                    "error": "Circuit breaker is open",
                    "circuit_state": self.circuit_breaker.state.value
                }
                await self.error_logger.log_error(
                    request_id=request.id,
                    error_message="Circuit breaker prevented execution",
                    category="circuit_breaker",
                    context={"extractor": self.extractor_name}
                )
                return self._finalize_result(result)
            
            # Update status
            result.status = ExtractionStatus.IN_PROGRESS
            
            # Execute with retry logic
            extracted_data = await self.retry_handler.execute_with_retry(
                operation=self._execute_extraction_with_circuit_breaker,
                operation_args=(request,),
                request_id=request.id,
                custom_config=request.retry_config
            )
            
            result.data = extracted_data
            result.total_records = len(extracted_data)
            result.processed_records = len(extracted_data)
            
            # Validate extracted data
            if request.validation_rules:
                validation_results = await self.validation_engine.validate_batch(
                    data=extracted_data,
                    rules=request.validation_rules
                )
                result.validation_results = validation_results
                
                # Count validation failures
                failed_validations = sum(
                    1 for record_results in validation_results.values()
                    if any(not r.get("is_valid", True) for r in record_results)
                )
                result.failed_records = failed_validations
                result.processed_records = result.total_records - failed_validations
            
            result.status = ExtractionStatus.COMPLETED
            logger.info("Extraction completed successfully", 
                       request_id=request.id,
                       records_extracted=result.total_records,
                       processing_time=result.processing_time_seconds)
            
        except Exception as e:
            result.status = ExtractionStatus.FAILED
            result.error_details = {
                "error": str(e),
                "error_type": type(e).__name__
            }
            
            # Log error with context
            await self.error_logger.log_error(
                request_id=request.id,
                error_message=str(e),
                error_type=type(e).__name__,
                category="extraction_failure",
                context={
                    "extractor": self.extractor_name,
                    "source": request.source,
                    "target": request.target,
                    "parameters": request.parameters
                }
            )
            
            logger.error("Extraction failed", 
                        request_id=request.id,
                        error=str(e),
                        error_type=type(e).__name__)
        
        return self._finalize_result(result)
    
    async def _execute_extraction_with_circuit_breaker(
        self,
        request: ExtractionRequest
    ) -> List[Dict[str, Any]]:
        """Execute extraction with circuit breaker protection"""
        try:
            # Mark circuit breaker as attempting
            await self.circuit_breaker.on_request()
            
            # Validate source connection
            if not await self._validate_source_connection():
                raise StarboardException("Source connection validation failed")
            
            # Perform extraction
            data = await self._extract_data(request)
            
            # Mark circuit breaker success
            await self.circuit_breaker.on_success()
            
            return data
            
        except Exception as e:
            # Mark circuit breaker failure
            await self.circuit_breaker.on_failure()
            raise
    
    def _finalize_result(self, result: ExtractionResult) -> ExtractionResult:
        """Finalize extraction result and update metrics"""
        result.completed_at = datetime.utcnow()
        
        if result.started_at:
            result.processing_time_seconds = (
                result.completed_at - result.started_at
            ).total_seconds()
        
        # Update metrics
        self.metrics.total_requests += 1
        if result.status == ExtractionStatus.COMPLETED:
            self.metrics.successful_requests += 1
            self.metrics.total_records_extracted += result.total_records
        else:
            self.metrics.failed_requests += 1
        
        self.metrics.retry_attempts += result.retry_count
        
        # Update average processing time
        if self.metrics.total_requests > 0:
            total_time = (
                self.metrics.average_processing_time * (self.metrics.total_requests - 1) +
                result.processing_time_seconds
            )
            self.metrics.average_processing_time = total_time / self.metrics.total_requests
        
        self.metrics.last_extraction_time = result.completed_at
        
        # Remove from active extractions
        if result.request_id in self.active_extractions:
            del self.active_extractions[result.request_id]
        
        return result
    
    async def extract_stream(
        self,
        request: ExtractionRequest,
        chunk_size: int = 100
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        """
        Stream extraction for large datasets
        
        Args:
            request: Extraction request
            chunk_size: Size of chunks to yield
            
        Yields:
            Chunks of extracted data
        """
        logger.info("Starting streaming extraction", 
                   request_id=request.id,
                   chunk_size=chunk_size)
        
        try:
            # Check circuit breaker
            if not await self.circuit_breaker.can_execute():
                raise StarboardException("Circuit breaker is open")
            
            # Validate source connection
            if not await self._validate_source_connection():
                raise StarboardException("Source connection validation failed")
            
            # Stream data in chunks
            current_chunk = []
            async for record in self._extract_data_stream(request):
                current_chunk.append(record)
                
                if len(current_chunk) >= chunk_size:
                    yield current_chunk
                    current_chunk = []
            
            # Yield remaining records
            if current_chunk:
                yield current_chunk
                
        except Exception as e:
            await self.error_logger.log_error(
                request_id=request.id,
                error_message=str(e),
                error_type=type(e).__name__,
                category="streaming_extraction_failure",
                context={
                    "extractor": self.extractor_name,
                    "chunk_size": chunk_size
                }
            )
            raise
    
    async def _extract_data_stream(
        self,
        request: ExtractionRequest
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Stream individual records - override for streaming support
        
        Args:
            request: Extraction request
            
        Yields:
            Individual extracted records
        """
        # Default implementation: extract all and yield one by one
        data = await self._extract_data(request)
        for record in data:
            yield record
    
    async def cancel_extraction(self, request_id: str) -> bool:
        """
        Cancel an active extraction
        
        Args:
            request_id: ID of extraction to cancel
            
        Returns:
            True if extraction was cancelled
        """
        if request_id in self.active_extractions:
            result = self.active_extractions[request_id]
            result.status = ExtractionStatus.CANCELLED
            result.completed_at = datetime.utcnow()
            
            logger.info("Extraction cancelled", request_id=request_id)
            return True
        
        return False
    
    def get_extraction_status(self, request_id: str) -> Optional[ExtractionResult]:
        """Get status of an extraction request"""
        return self.active_extractions.get(request_id)
    
    def get_metrics(self) -> ExtractionMetrics:
        """Get extractor metrics"""
        return self.metrics
    
    def get_active_extractions(self) -> Dict[str, ExtractionResult]:
        """Get all active extractions"""
        return self.active_extractions.copy()
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on the extractor
        
        Returns:
            Health status information
        """
        try:
            connection_valid = await self._validate_source_connection()
            circuit_state = self.circuit_breaker.state
            
            return {
                "extractor_name": self.extractor_name,
                "status": "healthy" if connection_valid else "unhealthy",
                "connection_valid": connection_valid,
                "circuit_breaker_state": circuit_state.value,
                "active_extractions": len(self.active_extractions),
                "metrics": self.metrics.dict(),
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            return {
                "extractor_name": self.extractor_name,
                "status": "error",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    async def shutdown(self):
        """Gracefully shutdown the extractor"""
        logger.info("Shutting down extractor", extractor_name=self.extractor_name)
        
        self._shutdown_event.set()
        
        # Cancel all active extractions
        for request_id in list(self.active_extractions.keys()):
            await self.cancel_extraction(request_id)
        
        # Close components
        await self.circuit_breaker.close()
        await self.error_logger.close()
        
        logger.info("Extractor shutdown complete", extractor_name=self.extractor_name) 