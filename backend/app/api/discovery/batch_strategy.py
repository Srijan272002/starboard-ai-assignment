"""
Batching Strategy - Intelligent batching for API requests
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable, TypeVar, Generic
from enum import Enum
import structlog
from pydantic import BaseModel, Field
from dataclasses import dataclass

from app.core.config import settings
from app.core.exceptions import StarboardException

logger = structlog.get_logger(__name__)

T = TypeVar('T')
R = TypeVar('R')


class BatchStrategy(str, Enum):
    """Batching strategies"""
    SIZE_BASED = "size_based"
    TIME_BASED = "time_based"
    PRIORITY_BASED = "priority_based"
    ADAPTIVE = "adaptive"


class BatchPriority(str, Enum):
    """Batch priority levels"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class BatchRequest:
    """Individual request in a batch"""
    id: str
    data: Any
    priority: BatchPriority = BatchPriority.NORMAL
    created_at: datetime = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow()
        if self.metadata is None:
            self.metadata = {}


class BatchConfig(BaseModel):
    """Batch configuration"""
    strategy: BatchStrategy = BatchStrategy.ADAPTIVE
    max_batch_size: int = 100
    max_wait_time: float = 30.0  # seconds
    min_batch_size: int = 1
    priority_weights: Dict[BatchPriority, float] = Field(default_factory=lambda: {
        BatchPriority.LOW: 0.25,
        BatchPriority.NORMAL: 1.0,
        BatchPriority.HIGH: 2.0,
        BatchPriority.CRITICAL: 4.0
    })
    adaptive_threshold: float = 0.8  # Trigger batch when queue reaches 80% capacity


class BatchResult(BaseModel, Generic[R]):
    """Result of batch processing"""
    batch_id: str
    total_requests: int
    successful_requests: int
    failed_requests: int
    processing_time: float
    results: List[R] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class BatchQueue:
    """Queue for managing batch requests"""
    
    def __init__(self, config: BatchConfig):
        self.config = config
        self.requests: List[BatchRequest] = []
        self.lock = asyncio.Lock()
        self._last_flush = datetime.utcnow()
    
    async def add_request(self, request: BatchRequest) -> bool:
        """
        Add a request to the batch queue
        
        Args:
            request: BatchRequest to add
            
        Returns:
            True if batch should be processed immediately
        """
        async with self.lock:
            self.requests.append(request)
            return self._should_process_batch()
    
    def _should_process_batch(self) -> bool:
        """Determine if batch should be processed"""
        if not self.requests:
            return False
        
        if self.config.strategy == BatchStrategy.SIZE_BASED:
            return len(self.requests) >= self.config.max_batch_size
        
        elif self.config.strategy == BatchStrategy.TIME_BASED:
            time_since_last = (datetime.utcnow() - self._last_flush).total_seconds()
            return time_since_last >= self.config.max_wait_time
        
        elif self.config.strategy == BatchStrategy.PRIORITY_BASED:
            # Process if we have high priority requests
            return any(req.priority in [BatchPriority.HIGH, BatchPriority.CRITICAL] 
                      for req in self.requests)
        
        elif self.config.strategy == BatchStrategy.ADAPTIVE:
            # Adaptive strategy considers multiple factors
            size_factor = len(self.requests) / self.config.max_batch_size
            time_factor = (datetime.utcnow() - self._last_flush).total_seconds() / self.config.max_wait_time
            
            # Check priority factor
            priority_score = sum(
                self.config.priority_weights.get(req.priority, 1.0) 
                for req in self.requests
            ) / len(self.requests)
            priority_factor = priority_score / self.config.priority_weights[BatchPriority.NORMAL]
            
            # Trigger if any factor exceeds threshold
            return (size_factor >= self.config.adaptive_threshold or 
                   time_factor >= 1.0 or 
                   priority_factor >= 2.0)
        
        return False
    
    async def get_batch(self) -> List[BatchRequest]:
        """Get current batch and clear queue"""
        async with self.lock:
            batch = self.requests.copy()
            self.requests.clear()
            self._last_flush = datetime.utcnow()
            return batch
    
    async def get_batch_by_priority(self) -> List[BatchRequest]:
        """Get batch sorted by priority"""
        async with self.lock:
            # Sort by priority (critical first) and creation time
            priority_order = {
                BatchPriority.CRITICAL: 0,
                BatchPriority.HIGH: 1,
                BatchPriority.NORMAL: 2,
                BatchPriority.LOW: 3
            }
            
            sorted_requests = sorted(
                self.requests,
                key=lambda x: (priority_order.get(x.priority, 2), x.created_at)
            )
            
            # Take up to max_batch_size requests
            batch = sorted_requests[:self.config.max_batch_size]
            
            # Remove batched requests from queue
            for req in batch:
                self.requests.remove(req)
            
            self._last_flush = datetime.utcnow()
            return batch
    
    def size(self) -> int:
        """Get current queue size"""
        return len(self.requests)
    
    def is_empty(self) -> bool:
        """Check if queue is empty"""
        return len(self.requests) == 0


class BatchingStrategy:
    """Intelligent batching strategy for API requests"""
    
    def __init__(self, config: Optional[BatchConfig] = None):
        self.config = config or BatchConfig()
        self.queues: Dict[str, BatchQueue] = {}
        self.processors: Dict[str, Callable] = {}
        self.active_batches: Dict[str, asyncio.Task] = {}
        self.stats: Dict[str, Dict[str, Any]] = {}
        self._processing_lock = asyncio.Lock()
    
    def create_queue(self, queue_name: str, config: Optional[BatchConfig] = None) -> BatchQueue:
        """
        Create a new batch queue
        
        Args:
            queue_name: Name of the queue
            config: Optional batch configuration
            
        Returns:
            BatchQueue instance
        """
        queue_config = config or self.config
        queue = BatchQueue(queue_config)
        self.queues[queue_name] = queue
        
        # Initialize stats
        self.stats[queue_name] = {
            "total_batches": 0,
            "total_requests": 0,
            "total_processing_time": 0.0,
            "average_batch_size": 0.0,
            "average_processing_time": 0.0,
            "last_batch_time": None
        }
        
        logger.info("Batch queue created", queue_name=queue_name, strategy=queue_config.strategy.value)
        return queue
    
    def register_processor(
        self,
        queue_name: str,
        processor: Callable[[List[BatchRequest]], Any]
    ):
        """
        Register a batch processor function
        
        Args:
            queue_name: Name of the queue
            processor: Function to process batches
        """
        self.processors[queue_name] = processor
        logger.info("Batch processor registered", queue_name=queue_name)
    
    async def add_request(
        self,
        queue_name: str,
        request_id: str,
        data: Any,
        priority: BatchPriority = BatchPriority.NORMAL,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[str]:
        """
        Add a request to a batch queue
        
        Args:
            queue_name: Name of the queue
            request_id: Unique identifier for the request
            data: Request data
            priority: Request priority
            metadata: Additional metadata
            
        Returns:
            Batch ID if batch was triggered, None otherwise
        """
        if queue_name not in self.queues:
            raise StarboardException(f"Queue {queue_name} not found")
        
        request = BatchRequest(
            id=request_id,
            data=data,
            priority=priority,
            metadata=metadata or {}
        )
        
        queue = self.queues[queue_name]
        should_process = await queue.add_request(request)
        
        if should_process:
            batch_id = f"{queue_name}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S_%f')}"
            task = asyncio.create_task(self._process_batch(queue_name, batch_id))
            self.active_batches[batch_id] = task
            return batch_id
        
        return None
    
    async def _process_batch(self, queue_name: str, batch_id: str) -> BatchResult:
        """Process a batch of requests"""
        async with self._processing_lock:
            start_time = datetime.utcnow()
            
            try:
                queue = self.queues[queue_name]
                processor = self.processors.get(queue_name)
                
                if not processor:
                    raise StarboardException(f"No processor registered for queue {queue_name}")
                
                # Get batch requests
                if queue.config.strategy == BatchStrategy.PRIORITY_BASED:
                    batch_requests = await queue.get_batch_by_priority()
                else:
                    batch_requests = await queue.get_batch()
                
                if not batch_requests:
                    logger.warning("Empty batch", queue_name=queue_name, batch_id=batch_id)
                    return BatchResult(
                        batch_id=batch_id,
                        total_requests=0,
                        successful_requests=0,
                        failed_requests=0,
                        processing_time=0.0
                    )
                
                logger.info("Processing batch", 
                           queue_name=queue_name,
                           batch_id=batch_id,
                           batch_size=len(batch_requests))
                
                # Process the batch
                results = []
                errors = []
                successful_count = 0
                
                try:
                    # Call the processor
                    if asyncio.iscoroutinefunction(processor):
                        batch_results = await processor(batch_requests)
                    else:
                        batch_results = processor(batch_requests)
                    
                    # Handle results
                    if isinstance(batch_results, list):
                        results = batch_results
                        successful_count = len([r for r in results if r is not None])
                    else:
                        results = [batch_results]
                        successful_count = 1 if batch_results is not None else 0
                        
                except Exception as e:
                    logger.error("Batch processing failed", 
                                queue_name=queue_name,
                                batch_id=batch_id,
                                error=str(e))
                    errors.append(str(e))
                
                # Calculate metrics
                processing_time = (datetime.utcnow() - start_time).total_seconds()
                failed_count = len(batch_requests) - successful_count
                
                result = BatchResult(
                    batch_id=batch_id,
                    total_requests=len(batch_requests),
                    successful_requests=successful_count,
                    failed_requests=failed_count,
                    processing_time=processing_time,
                    results=results,
                    errors=errors
                )
                
                # Update stats
                await self._update_stats(queue_name, result)
                
                logger.info("Batch processed", 
                           queue_name=queue_name,
                           batch_id=batch_id,
                           total_requests=result.total_requests,
                           successful_requests=result.successful_requests,
                           processing_time=result.processing_time)
                
                return result
                
            except Exception as e:
                logger.error("Batch processing error", 
                            queue_name=queue_name,
                            batch_id=batch_id,
                            error=str(e))
                raise
            finally:
                # Clean up
                if batch_id in self.active_batches:
                    del self.active_batches[batch_id]
    
    async def _update_stats(self, queue_name: str, result: BatchResult):
        """Update queue statistics"""
        stats = self.stats[queue_name]
        
        stats["total_batches"] += 1
        stats["total_requests"] += result.total_requests
        stats["total_processing_time"] += result.processing_time
        stats["last_batch_time"] = result.timestamp.isoformat()
        
        # Calculate averages
        if stats["total_batches"] > 0:
            stats["average_batch_size"] = stats["total_requests"] / stats["total_batches"]
            stats["average_processing_time"] = stats["total_processing_time"] / stats["total_batches"]
    
    async def force_process_queue(self, queue_name: str) -> Optional[str]:
        """
        Force processing of a queue regardless of batch conditions
        
        Args:
            queue_name: Name of the queue to process
            
        Returns:
            Batch ID if batch was created, None if queue was empty
        """
        if queue_name not in self.queues:
            raise StarboardException(f"Queue {queue_name} not found")
        
        queue = self.queues[queue_name]
        if queue.is_empty():
            return None
        
        batch_id = f"{queue_name}_forced_{datetime.utcnow().strftime('%Y%m%d_%H%M%S_%f')}"
        task = asyncio.create_task(self._process_batch(queue_name, batch_id))
        self.active_batches[batch_id] = task
        
        logger.info("Forced batch processing", queue_name=queue_name, batch_id=batch_id)
        return batch_id
    
    async def wait_for_batch(self, batch_id: str, timeout: Optional[float] = None) -> BatchResult:
        """
        Wait for a specific batch to complete
        
        Args:
            batch_id: ID of the batch to wait for
            timeout: Optional timeout in seconds
            
        Returns:
            BatchResult when complete
        """
        if batch_id not in self.active_batches:
            raise StarboardException(f"Batch {batch_id} not found or already completed")
        
        task = self.active_batches[batch_id]
        
        try:
            if timeout:
                result = await asyncio.wait_for(task, timeout=timeout)
            else:
                result = await task
            return result
        except asyncio.TimeoutError:
            logger.warning("Batch timeout", batch_id=batch_id, timeout=timeout)
            raise StarboardException(f"Batch {batch_id} timed out after {timeout} seconds")
    
    def get_queue_status(self, queue_name: str) -> Dict[str, Any]:
        """Get status information for a queue"""
        if queue_name not in self.queues:
            return {"error": "Queue not found"}
        
        queue = self.queues[queue_name]
        stats = self.stats.get(queue_name, {})
        
        # Count active batches for this queue
        active_batches = [
            batch_id for batch_id in self.active_batches.keys()
            if batch_id.startswith(queue_name)
        ]
        
        return {
            "queue_name": queue_name,
            "queue_size": queue.size(),
            "is_empty": queue.is_empty(),
            "strategy": queue.config.strategy.value,
            "max_batch_size": queue.config.max_batch_size,
            "max_wait_time": queue.config.max_wait_time,
            "active_batches": len(active_batches),
            "statistics": stats
        }
    
    def get_all_queue_status(self) -> Dict[str, Any]:
        """Get status for all queues"""
        return {
            queue_name: self.get_queue_status(queue_name)
            for queue_name in self.queues.keys()
        }
    
    async def close(self):
        """Close all queues and wait for active batches"""
        logger.info("Closing batching strategy")
        
        # Wait for all active batches to complete
        if self.active_batches:
            logger.info("Waiting for active batches", count=len(self.active_batches))
            await asyncio.gather(*self.active_batches.values(), return_exceptions=True)
        
        # Clear all data
        self.queues.clear()
        self.processors.clear()
        self.active_batches.clear()
        self.stats.clear()
        
        logger.info("Batching strategy closed") 