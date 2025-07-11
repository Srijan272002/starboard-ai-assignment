"""
Extraction Endpoints - API endpoints for Phase 3.1 Core Extraction Framework
"""

from typing import Dict, List, Optional, Any
from fastapi import APIRouter, HTTPException, BackgroundTasks, Query, Body
from pydantic import BaseModel, Field
import structlog
from datetime import datetime

from app.core.logging import get_logger
from app.api.extraction import (
    BaseExtractor,
    ExtractionRequest,
    ExtractionResult,
    ExtractionStatus,
    ExtractionPriority,
    RetryHandler,
    RetryConfig,
    CircuitBreaker,
    CircuitBreakerConfig,
    BatchProcessor,
    BatchProcessorConfig,
    ValidationEngine,
    ErrorLogger,
    ErrorCategory,
    ErrorSeverity
)

logger = get_logger(__name__)
router = APIRouter()

# Global instances (in production, these would be managed by dependency injection)
retry_handler = RetryHandler()
batch_processor = BatchProcessor()
validation_engine = ValidationEngine()


class ExtractionRequestModel(BaseModel):
    """API model for extraction requests"""
    source: str = Field(..., description="Data source identifier")
    target: str = Field(..., description="Target dataset or endpoint")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Extraction parameters")
    priority: ExtractionPriority = Field(default=ExtractionPriority.NORMAL)
    validation_rules: List[str] = Field(default_factory=list)
    retry_config: Optional[Dict[str, Any]] = Field(default=None)
    timeout_seconds: Optional[int] = Field(default=None)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class BatchExtractionRequest(BaseModel):
    """API model for batch extraction requests"""
    requests: List[ExtractionRequestModel]
    batch_config: Optional[Dict[str, Any]] = Field(default=None)


class ExtractionResponse(BaseModel):
    """API response for extraction operations"""
    success: bool
    message: str
    data: Optional[Any] = None
    error: Optional[str] = None
    request_id: Optional[str] = None
    extraction_id: Optional[str] = None


class ExtractionStatusResponse(BaseModel):
    """API response for extraction status"""
    request_id: str
    status: ExtractionStatus
    result: Optional[ExtractionResult] = None


class HealthCheckResponse(BaseModel):
    """API response for health check"""
    status: str
    timestamp: datetime
    components: Dict[str, Any]
    recommendations: List[str] = Field(default_factory=list)


# Sample extractor for demonstration
class SampleExtractor(BaseExtractor):
    """Sample extractor implementation for testing"""
    
    def __init__(self):
        super().__init__("sample_extractor")
    
    async def _extract_data(self, request: ExtractionRequest) -> List[Dict[str, Any]]:
        """Sample data extraction"""
        # Simulate data extraction
        import asyncio
        await asyncio.sleep(0.5)  # Simulate processing time
        
        return [
            {
                "id": f"sample_{i}",
                "source": request.source,
                "target": request.target,
                "data": f"Extracted data {i}",
                "timestamp": datetime.utcnow().isoformat()
            }
            for i in range(5)  # Return 5 sample records
        ]
    
    async def _validate_source_connection(self) -> bool:
        """Sample connection validation"""
        return True


# Initialize sample extractor
sample_extractor = SampleExtractor()


@router.post("/extract", response_model=ExtractionResponse)
async def extract_data(
    request: ExtractionRequestModel,
    background_tasks: BackgroundTasks
):
    """
    Extract data from a source
    """
    try:
        # Generate unique request ID
        request_id = f"req_{datetime.utcnow().strftime('%Y%m%d_%H%M%S_%f')}"
        
        # Create extraction request
        extraction_request = ExtractionRequest(
            id=request_id,
            source=request.source,
            target=request.target,
            parameters=request.parameters,
            priority=request.priority,
            validation_rules=request.validation_rules,
            retry_config=request.retry_config,
            timeout_seconds=request.timeout_seconds,
            metadata=request.metadata
        )
        
        logger.info("Extraction request received", 
                   request_id=request_id,
                   source=request.source,
                   target=request.target)
        
        # Start extraction in background
        background_tasks.add_task(
            perform_extraction,
            extraction_request
        )
        
        return ExtractionResponse(
            success=True,
            message="Extraction started",
            request_id=request_id,
            extraction_id=request_id
        )
        
    except Exception as e:
        logger.error("Failed to start extraction", error=str(e))
        return ExtractionResponse(
            success=False,
            message="Failed to start extraction",
            error=str(e)
        )


async def perform_extraction(request: ExtractionRequest):
    """Perform the actual extraction"""
    try:
        result = await sample_extractor.extract(request)
        logger.info("Extraction completed", 
                   request_id=request.id,
                   status=result.status.value)
    except Exception as e:
        logger.error("Extraction failed", 
                    request_id=request.id,
                    error=str(e))


@router.post("/extract/batch", response_model=ExtractionResponse)
async def extract_batch(
    request: BatchExtractionRequest,
    background_tasks: BackgroundTasks
):
    """
    Extract data from multiple sources in batch
    """
    try:
        if not batch_processor.processing_task:
            await batch_processor.start()
        
        batch_id = None
        added_requests = 0
        
        for req_model in request.requests:
            # Generate unique request ID
            request_id = f"req_{datetime.utcnow().strftime('%Y%m%d_%H%M%S_%f')}_{added_requests}"
            
            # Create extraction request
            extraction_request = ExtractionRequest(
                id=request_id,
                source=req_model.source,
                target=req_model.target,
                parameters=req_model.parameters,
                priority=req_model.priority,
                validation_rules=req_model.validation_rules,
                retry_config=req_model.retry_config,
                timeout_seconds=req_model.timeout_seconds,
                metadata=req_model.metadata
            )
            
            # Add to batch processor
            returned_batch_id = await batch_processor.add_request(
                extraction_request,
                priority=req_model.priority
            )
            
            if returned_batch_id:
                batch_id = returned_batch_id
            
            added_requests += 1
        
        logger.info("Batch extraction request received", 
                   total_requests=added_requests,
                   batch_id=batch_id)
        
        return ExtractionResponse(
            success=True,
            message=f"Batch extraction started with {added_requests} requests",
            extraction_id=batch_id,
            data={"requests_added": added_requests, "batch_id": batch_id}
        )
        
    except Exception as e:
        logger.error("Failed to start batch extraction", error=str(e))
        return ExtractionResponse(
            success=False,
            message="Failed to start batch extraction",
            error=str(e)
        )


@router.get("/extract/{request_id}/status", response_model=ExtractionStatusResponse)
async def get_extraction_status(request_id: str):
    """
    Get status of an extraction request
    """
    try:
        # Check in active extractions
        result = sample_extractor.get_extraction_status(request_id)
        
        if result:
            return ExtractionStatusResponse(
                request_id=request_id,
                status=result.status,
                result=result
            )
        
        # Check in batch processor
        # For simplicity, we'll return a not found response
        raise HTTPException(status_code=404, detail="Extraction request not found")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get extraction status", 
                    request_id=request_id,
                    error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get extraction status")


@router.post("/extract/{request_id}/cancel", response_model=ExtractionResponse)
async def cancel_extraction(request_id: str):
    """
    Cancel an active extraction request
    """
    try:
        cancelled = await sample_extractor.cancel_extraction(request_id)
        
        if not cancelled:
            # Try batch processor
            cancelled = await batch_processor.cancel_batch(request_id)
        
        if cancelled:
            return ExtractionResponse(
                success=True,
                message="Extraction cancelled",
                request_id=request_id
            )
        else:
            return ExtractionResponse(
                success=False,
                message="Extraction not found or already completed",
                request_id=request_id
            )
        
    except Exception as e:
        logger.error("Failed to cancel extraction", 
                    request_id=request_id,
                    error=str(e))
        return ExtractionResponse(
            success=False,
            message="Failed to cancel extraction",
            error=str(e),
            request_id=request_id
        )


@router.get("/batch/status", response_model=Dict[str, Any])
async def get_batch_status():
    """
    Get current batch processor status
    """
    try:
        return batch_processor.get_status()
    except Exception as e:
        logger.error("Failed to get batch status", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get batch status")


@router.get("/batch/{batch_id}/status", response_model=Dict[str, Any])
async def get_batch_status_by_id(batch_id: str):
    """
    Get status of a specific batch
    """
    try:
        status = batch_processor.get_batch_status(batch_id)
        
        if status:
            return status
        else:
            raise HTTPException(status_code=404, detail="Batch not found")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get batch status", 
                    batch_id=batch_id,
                    error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get batch status")


@router.get("/retry/stats", response_model=Dict[str, Any])
async def get_retry_stats(request_id: Optional[str] = Query(None)):
    """
    Get retry statistics
    """
    try:
        return retry_handler.get_retry_stats(request_id)
    except Exception as e:
        logger.error("Failed to get retry stats", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get retry stats")


@router.post("/retry/test", response_model=Dict[str, Any])
async def test_retry_config(config: Optional[Dict[str, Any]] = Body(None)):
    """
    Test retry configuration
    """
    try:
        if config:
            from app.api.extraction.retry_handler import RetryConfig
            retry_config = RetryConfig(**config)
        else:
            retry_config = None
        
        results = await retry_handler.test_retry_configuration(retry_config)
        return results
        
    except Exception as e:
        logger.error("Failed to test retry config", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to test retry config")


@router.get("/validation/rules", response_model=Dict[str, Any])
async def get_validation_rules():
    """
    Get validation rules summary
    """
    try:
        return validation_engine.get_rules_summary()
    except Exception as e:
        logger.error("Failed to get validation rules", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get validation rules")


@router.post("/validation/validate", response_model=Dict[str, Any])
async def validate_data(
    data: List[Dict[str, Any]] = Body(...),
    rules: Optional[List[str]] = Body(None)
):
    """
    Validate data records
    """
    try:
        results = await validation_engine.validate_batch(data, rules)
        
        # Convert results to serializable format
        serializable_results = {}
        for record_id, report in results.items():
            serializable_results[record_id] = report.dict()
        
        return {
            "validation_results": serializable_results,
            "summary": {
                "total_records": len(data),
                "valid_records": sum(1 for r in results.values() if r.is_valid),
                "invalid_records": sum(1 for r in results.values() if not r.is_valid)
            }
        }
        
    except Exception as e:
        logger.error("Failed to validate data", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to validate data")


@router.get("/errors/recent", response_model=List[Dict[str, Any]])
async def get_recent_errors(
    hours: int = Query(24, ge=1, le=168),
    category: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000)
):
    """
    Get recent errors from the error logger
    """
    try:
        # Convert string parameters to enums
        error_category = None
        if category:
            try:
                error_category = ErrorCategory(category)
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid category: {category}")
        
        error_severity = None
        if severity:
            try:
                error_severity = ErrorSeverity(severity)
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid severity: {severity}")
        
        # Get errors from sample extractor's error logger
        errors = sample_extractor.error_logger.get_recent_errors(
            hours=hours,
            category=error_category,
            severity=error_severity,
            limit=limit
        )
        
        return [error.dict() for error in errors]
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get recent errors", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get recent errors")


@router.get("/errors/stats", response_model=Dict[str, Any])
async def get_error_stats():
    """
    Get error statistics
    """
    try:
        stats = sample_extractor.error_logger.get_error_stats()
        return stats.dict()
    except Exception as e:
        logger.error("Failed to get error stats", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get error stats")


@router.get("/errors/patterns", response_model=Dict[str, Any])
async def get_error_patterns():
    """
    Get error patterns status
    """
    try:
        return sample_extractor.error_logger.get_error_patterns_status()
    except Exception as e:
        logger.error("Failed to get error patterns", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get error patterns")


@router.get("/health", response_model=HealthCheckResponse)
async def health_check():
    """
    Comprehensive health check for extraction framework
    """
    try:
        components = {}
        recommendations = []
        overall_status = "healthy"
        
        # Check extractor health
        extractor_health = await sample_extractor.health_check()
        components["extractor"] = extractor_health
        
        if extractor_health.get("status") != "healthy":
            overall_status = "degraded"
            recommendations.append("Extractor health issues detected")
        
        # Check batch processor health
        batch_health = await batch_processor.health_check()
        components["batch_processor"] = batch_health
        
        if batch_health.get("status") not in ["healthy", "busy"]:
            overall_status = "degraded"
            recommendations.extend(batch_health.get("recommendations", []))
        
        # Check circuit breaker health
        circuit_health = await sample_extractor.circuit_breaker.health_check()
        components["circuit_breaker"] = circuit_health
        
        if circuit_health.get("status") == "unhealthy":
            overall_status = "unhealthy"
            recommendations.extend(circuit_health.get("recommendations", []))
        
        # Check metrics
        extractor_metrics = sample_extractor.get_metrics()
        components["metrics"] = extractor_metrics.dict()
        
        # Check error patterns
        error_patterns = sample_extractor.error_logger.get_error_patterns_status()
        components["error_patterns"] = error_patterns
        
        # Check for critical error patterns
        critical_patterns = [
            pattern for pattern in error_patterns.values()
            if pattern.get("threshold_reached", False)
        ]
        
        if critical_patterns:
            overall_status = "unhealthy"
            recommendations.append(f"{len(critical_patterns)} error patterns have reached threshold")
        
        return HealthCheckResponse(
            status=overall_status,
            timestamp=datetime.utcnow(),
            components=components,
            recommendations=recommendations
        )
        
    except Exception as e:
        logger.error("Health check failed", error=str(e))
        return HealthCheckResponse(
            status="error",
            timestamp=datetime.utcnow(),
            components={"error": str(e)},
            recommendations=["Health check system failure - investigate immediately"]
        )


@router.get("/metrics", response_model=Dict[str, Any])
async def get_metrics():
    """
    Get comprehensive metrics for the extraction framework
    """
    try:
        return {
            "extractor_metrics": sample_extractor.get_metrics().dict(),
            "batch_processor_status": batch_processor.get_status(),
            "retry_stats": retry_handler.get_retry_stats(),
            "error_stats": sample_extractor.error_logger.get_error_stats().dict(),
            "circuit_breaker_status": sample_extractor.circuit_breaker.get_status(),
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error("Failed to get metrics", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get metrics")


# Startup event to initialize batch processor
@router.on_event("startup")
async def startup_event():
    """Initialize extraction framework components"""
    try:
        await batch_processor.start()
        logger.info("Extraction framework initialized successfully")
    except Exception as e:
        logger.error("Failed to initialize extraction framework", error=str(e))


# Shutdown event to clean up resources
@router.on_event("shutdown") 
async def shutdown_event():
    """Clean up extraction framework components"""
    try:
        await batch_processor.stop()
        await sample_extractor.shutdown()
        logger.info("Extraction framework shutdown complete")
    except Exception as e:
        logger.error("Error during extraction framework shutdown", error=str(e)) 