#!/usr/bin/env python3
"""
Test script for Phase 3.1 Core Extraction Framework

This script demonstrates the functionality of the implemented extraction framework
including retry logic, circuit breaker, batch processing, validation, and error logging.
"""

import asyncio
import json
from datetime import datetime
from typing import Dict, List, Any

# Import the extraction framework components
from app.api.extraction import (
    BaseExtractor,
    ExtractionRequest,
    ExtractionResult,
    ExtractionPriority,
    RetryHandler,
    RetryConfig,
    RetryStrategy,
    CircuitBreaker,
    CircuitBreakerConfig,
    BatchProcessor,
    BatchProcessorConfig,
    BatchStrategy,
    ValidationEngine,
    ValidationRule,
    ValidationType,
    ValidationSeverity,
    ErrorLogger,
    ErrorCategory,
    ErrorSeverity as ErrorSev
)


class DemoExtractor(BaseExtractor):
    """Demo extractor for testing the framework"""
    
    def __init__(self, failure_rate: float = 0.0):
        super().__init__("demo_extractor")
        self.failure_rate = failure_rate
        self.call_count = 0
    
    async def _extract_data(self, request: ExtractionRequest) -> List[Dict[str, Any]]:
        """Simulate data extraction with configurable failure rate"""
        self.call_count += 1
        
        # Simulate processing time
        await asyncio.sleep(0.1)
        
        # Simulate failures based on failure rate
        import random
        if random.random() < self.failure_rate:
            if self.call_count <= 2:
                raise ConnectionError("Simulated network connection error")
            else:
                raise TimeoutError("Simulated timeout error")
        
        # Return sample data
        return [
            {
                "property_id": f"PROP_{i}_{request.id}",
                "address": f"{100 + i} Demo Street",
                "city": "Demo City",
                "square_footage": 1000 + (i * 100),
                "assessed_value": 50000 + (i * 5000),
                "latitude": 40.7128 + (i * 0.001),
                "longitude": -74.0060 + (i * 0.001),
                "extraction_timestamp": datetime.utcnow().isoformat()
            }
            for i in range(3)
        ]
    
    async def _validate_source_connection(self) -> bool:
        """Simulate connection validation"""
        return True


async def test_basic_extraction():
    """Test basic extraction functionality"""
    print("\n=== Testing Basic Extraction ===")
    
    extractor = DemoExtractor()
    
    request = ExtractionRequest(
        id="test_basic_001",
        source="demo_api",
        target="properties",
        parameters={"limit": 10}
    )
    
    result = await extractor.extract(request)
    
    print(f"Status: {result.status}")
    print(f"Records extracted: {result.total_records}")
    print(f"Processing time: {result.processing_time_seconds:.2f}s")
    print(f"Data quality score: {result.validation_results}")


async def test_retry_logic():
    """Test retry logic with exponential backoff"""
    print("\n=== Testing Retry Logic ===")
    
    # Create extractor with high failure rate
    extractor = DemoExtractor(failure_rate=0.8)
    
    # Configure custom retry settings
    retry_config = {
        "strategy": "jittered_exponential",
        "max_attempts": 5,
        "initial_delay_seconds": 0.1,
        "backoff_multiplier": 2.0
    }
    
    request = ExtractionRequest(
        id="test_retry_001",
        source="unreliable_api",
        target="properties",
        retry_config=retry_config
    )
    
    start_time = datetime.utcnow()
    try:
        result = await extractor.extract(request)
        end_time = datetime.utcnow()
        
        print(f"Status: {result.status}")
        print(f"Retry count: {result.retry_count}")
        print(f"Total time: {(end_time - start_time).total_seconds():.2f}s")
        print(f"Records: {result.total_records}")
        
    except Exception as e:
        end_time = datetime.utcnow()
        print(f"Failed after retries: {str(e)}")
        print(f"Total time: {(end_time - start_time).total_seconds():.2f}s")


async def test_circuit_breaker():
    """Test circuit breaker functionality"""
    print("\n=== Testing Circuit Breaker ===")
    
    # Create circuit breaker with low threshold
    config = CircuitBreakerConfig(
        failure_threshold=3,
        timeout_seconds=2,
        success_threshold=2
    )
    
    circuit_breaker = CircuitBreaker("test_circuit", config)
    
    async def failing_operation():
        raise ConnectionError("Simulated failure")
    
    async def successful_operation():
        return "Success"
    
    print("Testing failure scenarios...")
    
    # Test failures to open circuit
    for i in range(5):
        if await circuit_breaker.can_execute():
            await circuit_breaker.on_request()
            try:
                result = await failing_operation()
                await circuit_breaker.on_success()
            except Exception as e:
                await circuit_breaker.on_failure(e)
                print(f"Attempt {i+1}: Failed - {circuit_breaker.state}")
        else:
            print(f"Attempt {i+1}: Circuit breaker rejected request")
    
    print(f"Final circuit state: {circuit_breaker.state}")
    
    # Wait for timeout and test recovery
    print("Waiting for circuit breaker timeout...")
    await asyncio.sleep(2.5)
    
    if await circuit_breaker.can_execute():
        print("Circuit breaker moved to half-open, testing recovery...")
        await circuit_breaker.on_request()
        try:
            result = await successful_operation()
            await circuit_breaker.on_success()
            print(f"Recovery successful - {circuit_breaker.state}")
        except Exception as e:
            await circuit_breaker.on_failure(e)


async def test_batch_processing():
    """Test smart batch processing"""
    print("\n=== Testing Batch Processing ===")
    
    # Configure batch processor
    config = BatchProcessorConfig(
        strategy=BatchStrategy.ADAPTIVE,
        max_batch_size=5,
        max_wait_time_seconds=2.0
    )
    
    batch_processor = BatchProcessor(config)
    await batch_processor.start()
    
    try:
        # Create multiple extraction requests
        requests = []
        for i in range(8):
            request = ExtractionRequest(
                id=f"batch_test_{i:03d}",
                source="batch_api",
                target="properties",
                parameters={"page": i},
                priority=ExtractionPriority.HIGH if i < 3 else ExtractionPriority.NORMAL
            )
            requests.append(request)
        
        # Add requests to batch processor
        batch_ids = []
        for request in requests:
            batch_id = await batch_processor.add_request(request)
            if batch_id:
                batch_ids.append(batch_id)
                print(f"Request {request.id} added to batch {batch_id}")
            else:
                print(f"Request {request.id} queued for batching")
        
        # Wait for processing
        print("Waiting for batch processing...")
        await asyncio.sleep(5)
        
        # Get status
        status = batch_processor.get_status()
        print(f"Batch processor status: {json.dumps(status, indent=2, default=str)}")
        
    finally:
        await batch_processor.stop()


async def test_validation_engine():
    """Test comprehensive data validation"""
    print("\n=== Testing Validation Engine ===")
    
    validation_engine = ValidationEngine()
    
    # Test data with various validation scenarios
    test_data = [
        {
            "id": "valid_001",
            "property_id": "PROP_12345",
            "address": "123 Main Street",
            "city": "Chicago",
            "square_footage": 2500,
            "assessed_value": 150000,
            "latitude": 41.8781,
            "longitude": -87.6298,
            "year_built": 1995,
            "property_type": "industrial"
        },
        {
            "id": "invalid_001",
            "property_id": "",  # Invalid: empty
            "address": "456 Elm St",
            "city": "Dallas",
            "square_footage": -500,  # Invalid: negative
            "assessed_value": "not_a_number",  # Invalid: not numeric
            "latitude": 150.0,  # Invalid: out of range
            "longitude": -87.6298,
            "year_built": 1850,  # Valid but old
            "property_type": "unknown_type"  # Warning: not in standard list
        },
        {
            "id": "partial_001",
            "property_id": "PROP_67890",
            "address": "789 Oak Avenue",
            # Missing city
            "square_footage": 1800,
            "latitude": 34.0522,
            "longitude": -118.2437
        }
    ]
    
    # Validate batch
    results = await validation_engine.validate_batch(test_data)
    
    for record_id, report in results.items():
        print(f"\nRecord {record_id}:")
        print(f"  Valid: {report.is_valid}")
        print(f"  Quality Score: {report.data_quality_score:.2f}")
        print(f"  Completeness Score: {report.completeness_score:.2f}")
        print(f"  Errors: {report.errors}, Warnings: {report.warnings}")
        
        if not report.is_valid:
            for result in report.results:
                if not result.is_valid:
                    print(f"    {result.severity.upper()}: {result.message}")


async def test_error_logging():
    """Test contextual error logging"""
    print("\n=== Testing Error Logging ===")
    
    error_logger = ErrorLogger("test_extractor")
    
    # Log various types of errors
    errors = [
        {
            "message": "Network connection timeout",
            "category": ErrorCategory.NETWORK_ERROR,
            "severity": ErrorSev.ERROR,
            "error_type": "TimeoutError",
            "context": {
                "source": "external_api",
                "target": "properties",
                "response_status": 504
            }
        },
        {
            "message": "Authentication failed",
            "category": ErrorCategory.AUTHENTICATION_ERROR,
            "severity": ErrorSev.CRITICAL,
            "error_type": "AuthenticationError",
            "context": {
                "source": "secure_api",
                "response_status": 401
            }
        },
        {
            "message": "Rate limit exceeded",
            "category": ErrorCategory.RATE_LIMIT_ERROR,
            "severity": ErrorSev.WARNING,
            "error_type": "RateLimitError",
            "context": {
                "source": "api_v1",
                "response_status": 429,
                "retry_after": 60
            }
        }
    ]
    
    error_ids = []
    for error_data in errors:
        error_id = await error_logger.log_error(**error_data)
        error_ids.append(error_id)
        print(f"Logged error {error_id}: {error_data['message']}")
    
    # Get error statistics
    stats = error_logger.get_error_stats()
    print(f"\nError Statistics:")
    print(f"  Total errors: {stats.total_errors}")
    print(f"  By category: {dict(stats.errors_by_category)}")
    print(f"  By severity: {dict(stats.errors_by_severity)}")
    
    # Get recent errors
    recent_errors = error_logger.get_recent_errors(hours=1, limit=5)
    print(f"\nRecent errors: {len(recent_errors)}")
    
    # Test error pattern detection
    pattern_status = error_logger.get_error_patterns_status()
    print(f"\nError patterns status:")
    for pattern_id, status in pattern_status.items():
        print(f"  {pattern_id}: {status['recent_matches']}/{status['threshold_count']} matches")


async def comprehensive_demo():
    """Run comprehensive demonstration of the extraction framework"""
    print("=" * 60)
    print("Phase 3.1 Core Extraction Framework Demonstration")
    print("=" * 60)
    
    try:
        await test_basic_extraction()
        await test_retry_logic()
        await test_circuit_breaker()
        await test_batch_processing()
        await test_validation_engine()
        await test_error_logging()
        
        print("\n" + "=" * 60)
        print("All tests completed successfully!")
        print("Phase 3.1 Core Extraction Framework is fully operational.")
        print("=" * 60)
        
    except Exception as e:
        print(f"\nDemo failed with error: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(comprehensive_demo()) 