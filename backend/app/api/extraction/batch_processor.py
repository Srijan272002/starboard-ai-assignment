"""
Batch Processor - Smart batch processing system for data extraction
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable, Union, AsyncGenerator
from enum import Enum
import structlog
from pydantic import BaseModel, Field
from dataclasses import dataclass

from app.core.config import settings
from app.core.exceptions import StarboardException
from .base_extractor import ExtractionRequest, ExtractionResult

logger = structlog.get_logger(__name__)


class BatchStrategy(str, Enum):
    """Batch processing strategies"""
    SIZE_BASED = "size_based"
    TIME_BASED = "time_based"
    PRIORITY_BASED = "priority_based"
    ADAPTIVE = "adaptive"
    RESOURCE_AWARE = "resource_aware"


class BatchPriority(str, Enum):
    """Batch priority levels"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class BatchProcessorConfig(BaseModel):
    """Configuration for batch processor"""
    strategy: BatchStrategy = BatchStrategy.ADAPTIVE
    max_batch_size: int = 100
    min_batch_size: int = 1
    max_wait_time_seconds: float = 30.0
    priority_weights: Dict[BatchPriority, float] = Field(default_factory=lambda: {
        BatchPriority.LOW: 0.25,
        BatchPriority.NORMAL: 1.0,
        BatchPriority.HIGH: 2.0,
        BatchPriority.CRITICAL: 4.0
    })
    max_concurrent_batches: int = 5
    adaptive_threshold: float = 0.8  # Trigger batch when queue reaches 80% capacity
    resource_threshold_cpu: float = 0.7  # CPU usage threshold
    resource_threshold_memory: float = 0.8  # Memory usage threshold
    enable_compression: bool = True
    enable_deduplication: bool = True


class BatchItem(BaseModel):
    """Item in a batch"""
    request: ExtractionRequest
    priority: BatchPriority = BatchPriority.NORMAL
    created_at: datetime = Field(default_factory=datetime.utcnow)
    estimated_processing_time: Optional[float] = None
    dependencies: List[str] = Field(default_factory=list)  # Request IDs this depends on
    metadata: Dict[str, Any] = Field(default_factory=dict)


class BatchStatus(str, Enum):
    """Status of batch processing"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PARTIAL = "partial"  # Some items completed, some failed


class Batch(BaseModel):
    """A batch of extraction requests"""
    id: str
    items: List[BatchItem] = Field(default_factory=list)
    status: BatchStatus = BatchStatus.PENDING
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    processing_time_seconds: float = 0.0
    results: List[ExtractionResult] = Field(default_factory=list)
    error_details: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class BatchMetrics(BaseModel):
    """Metrics for batch processing"""
    total_batches: int = 0
    completed_batches: int = 0
    failed_batches: int = 0
    total_items_processed: int = 0
    average_batch_size: float = 0.0
    average_processing_time: float = 0.0
    average_wait_time: float = 0.0
    throughput_items_per_second: float = 0.0
    success_rate: float = 0.0


class ResourceMonitor:
    """Monitor system resources for adaptive batching"""
    
    def __init__(self):
        self.cpu_usage: float = 0.0
        self.memory_usage: float = 0.0
        self.last_update: datetime = datetime.utcnow()
    
    async def update_metrics(self):
        """Update resource metrics"""
        try:
            import psutil
            self.cpu_usage = psutil.cpu_percent(interval=0.1) / 100.0
            self.memory_usage = psutil.virtual_memory().percent / 100.0
            self.last_update = datetime.utcnow()
        except ImportError:
            # Fallback if psutil not available
            self.cpu_usage = 0.5  # Assume moderate usage
            self.memory_usage = 0.5
    
    def get_resource_pressure(self) -> float:
        """Get current resource pressure (0.0 to 1.0)"""
        return max(self.cpu_usage, self.memory_usage)
    
    def should_reduce_batch_size(self, threshold_cpu: float, threshold_memory: float) -> bool:
        """Determine if batch size should be reduced due to resource pressure"""
        return self.cpu_usage > threshold_cpu or self.memory_usage > threshold_memory


class BatchProcessor:
    """Smart batch processor for extraction requests"""
    
    def __init__(self, config: Optional[BatchProcessorConfig] = None):
        self.config = config or BatchProcessorConfig()
        self.metrics = BatchMetrics()
        self.resource_monitor = ResourceMonitor()
        
        # State management
        self.pending_items: List[BatchItem] = []
        self.active_batches: Dict[str, Batch] = {}
        self.completed_batches: List[Batch] = []
        self.processing_semaphore = asyncio.Semaphore(self.config.max_concurrent_batches)
        
        # Deduplication cache
        self.deduplication_cache: Dict[str, str] = {}  # hash -> batch_id
        
        # Processing task
        self.processing_task: Optional[asyncio.Task] = None
        self.shutdown_event = asyncio.Event()
        
        logger.info("Batch processor initialized", 
                   strategy=self.config.strategy.value,
                   max_batch_size=self.config.max_batch_size)
    
    async def start(self):
        """Start the batch processor"""
        if self.processing_task and not self.processing_task.done():
            logger.warning("Batch processor already running")
            return
        
        self.processing_task = asyncio.create_task(self._processing_loop())
        logger.info("Batch processor started")
    
    async def stop(self):
        """Stop the batch processor"""
        self.shutdown_event.set()
        
        if self.processing_task:
            try:
                await self.processing_task
            except asyncio.CancelledError:
                pass
        
        # Cancel active batches
        for batch in self.active_batches.values():
            batch.status = BatchStatus.CANCELLED
        
        logger.info("Batch processor stopped")
    
    async def add_request(
        self,
        request: ExtractionRequest,
        priority: BatchPriority = BatchPriority.NORMAL,
        estimated_processing_time: Optional[float] = None,
        dependencies: Optional[List[str]] = None
    ) -> str:
        """
        Add a request to the batch queue
        
        Args:
            request: Extraction request
            priority: Priority level
            estimated_processing_time: Expected processing time in seconds
            dependencies: List of request IDs this request depends on
            
        Returns:
            Batch ID if request was added to an existing batch, None if queued
        """
        # Check for deduplication
        if self.config.enable_deduplication:
            request_hash = self._calculate_request_hash(request)
            if request_hash in self.deduplication_cache:
                existing_batch_id = self.deduplication_cache[request_hash]
                logger.debug("Request deduplicated", 
                           request_id=request.id,
                           existing_batch_id=existing_batch_id)
                return existing_batch_id
        
        # Create batch item
        item = BatchItem(
            request=request,
            priority=priority,
            estimated_processing_time=estimated_processing_time,
            dependencies=dependencies or []
        )
        
        self.pending_items.append(item)
        
        logger.debug("Request added to batch queue", 
                    request_id=request.id,
                    priority=priority.value,
                    queue_size=len(self.pending_items))
        
        # Check if we should immediately process a batch
        if await self._should_process_batch():
            batch = await self._create_batch()
            if batch:
                asyncio.create_task(self._process_batch(batch))
                return batch.id
        
        return None
    
    async def _processing_loop(self):
        """Main processing loop"""
        while not self.shutdown_event.is_set():
            try:
                # Update resource metrics
                await self.resource_monitor.update_metrics()
                
                # Check if we should process a batch
                if await self._should_process_batch():
                    batch = await self._create_batch()
                    if batch:
                        # Process batch asynchronously
                        asyncio.create_task(self._process_batch(batch))
                
                # Wait before next check
                await asyncio.sleep(1.0)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error in batch processing loop", error=str(e))
                await asyncio.sleep(5.0)  # Back off on error
    
    async def _should_process_batch(self) -> bool:
        """Determine if we should process a batch now"""
        if not self.pending_items:
            return False
        
        # Check if we have available processing capacity
        if len(self.active_batches) >= self.config.max_concurrent_batches:
            return False
        
        if self.config.strategy == BatchStrategy.SIZE_BASED:
            return len(self.pending_items) >= self.config.max_batch_size
        
        elif self.config.strategy == BatchStrategy.TIME_BASED:
            oldest_item = min(self.pending_items, key=lambda x: x.created_at)
            wait_time = (datetime.utcnow() - oldest_item.created_at).total_seconds()
            return wait_time >= self.config.max_wait_time_seconds
        
        elif self.config.strategy == BatchStrategy.PRIORITY_BASED:
            # Check for high priority items
            return any(item.priority in [BatchPriority.HIGH, BatchPriority.CRITICAL] 
                      for item in self.pending_items)
        
        elif self.config.strategy == BatchStrategy.RESOURCE_AWARE:
            # Consider resource pressure
            resource_pressure = self.resource_monitor.get_resource_pressure()
            if resource_pressure > 0.8:
                return len(self.pending_items) >= self.config.min_batch_size
            else:
                return len(self.pending_items) >= self.config.max_batch_size
        
        elif self.config.strategy == BatchStrategy.ADAPTIVE:
            # Adaptive strategy considers multiple factors
            size_factor = len(self.pending_items) / self.config.max_batch_size
            
            oldest_item = min(self.pending_items, key=lambda x: x.created_at)
            time_factor = (datetime.utcnow() - oldest_item.created_at).total_seconds() / self.config.max_wait_time_seconds
            
            # Check priority factor
            priority_score = sum(
                self.config.priority_weights.get(item.priority, 1.0) 
                for item in self.pending_items
            ) / len(self.pending_items)
            priority_factor = priority_score / self.config.priority_weights[BatchPriority.NORMAL]
            
            # Resource factor
            resource_pressure = self.resource_monitor.get_resource_pressure()
            resource_factor = 1.0 - resource_pressure  # Lower resource pressure = higher factor
            
            # Weighted decision
            decision_score = (
                size_factor * 0.3 +
                time_factor * 0.3 +
                priority_factor * 0.3 +
                resource_factor * 0.1
            )
            
            return decision_score >= self.config.adaptive_threshold
        
        return False
    
    async def _create_batch(self) -> Optional[Batch]:
        """Create a batch from pending items"""
        if not self.pending_items:
            return None
        
        # Determine batch size based on strategy and resources
        max_size = self._calculate_optimal_batch_size()
        
        # Sort pending items by priority and creation time
        sorted_items = sorted(
            self.pending_items,
            key=lambda x: (
                -self.config.priority_weights.get(x.priority, 1.0),
                x.created_at
            )
        )
        
        # Select items for batch, respecting dependencies
        selected_items = []
        processed_dependencies = set()
        
        for item in sorted_items:
            if len(selected_items) >= max_size:
                break
            
            # Check dependencies
            if all(dep_id in processed_dependencies for dep_id in item.dependencies):
                selected_items.append(item)
                processed_dependencies.add(item.request.id)
                self.pending_items.remove(item)
        
        if not selected_items:
            return None
        
        # Create batch
        batch_id = f"batch_{datetime.utcnow().strftime('%Y%m%d_%H%M%S_%f')}"
        batch = Batch(
            id=batch_id,
            items=selected_items,
            metadata={
                "strategy": self.config.strategy.value,
                "optimal_size": max_size,
                "resource_pressure": self.resource_monitor.get_resource_pressure()
            }
        )
        
        # Update deduplication cache
        if self.config.enable_deduplication:
            for item in selected_items:
                request_hash = self._calculate_request_hash(item.request)
                self.deduplication_cache[request_hash] = batch_id
        
        logger.info("Batch created", 
                   batch_id=batch_id,
                   size=len(selected_items),
                   strategy=self.config.strategy.value)
        
        return batch
    
    def _calculate_optimal_batch_size(self) -> int:
        """Calculate optimal batch size based on current conditions"""
        base_size = self.config.max_batch_size
        
        # Adjust based on resource pressure
        resource_pressure = self.resource_monitor.get_resource_pressure()
        if resource_pressure > self.config.resource_threshold_cpu:
            # Reduce batch size under high resource pressure
            base_size = max(
                self.config.min_batch_size,
                int(base_size * (1.0 - resource_pressure))
            )
        
        # Adjust based on active batches
        active_batch_ratio = len(self.active_batches) / self.config.max_concurrent_batches
        if active_batch_ratio > 0.8:
            base_size = max(
                self.config.min_batch_size,
                int(base_size * 0.7)  # Reduce size when near capacity
            )
        
        return min(base_size, len(self.pending_items))
    
    async def _process_batch(self, batch: Batch):
        """Process a batch of requests"""
        async with self.processing_semaphore:
            batch.status = BatchStatus.PROCESSING
            batch.started_at = datetime.utcnow()
            self.active_batches[batch.id] = batch
            
            logger.info("Starting batch processing", 
                       batch_id=batch.id,
                       size=len(batch.items))
            
            try:
                # Process items in the batch
                results = []
                successful_count = 0
                failed_count = 0
                
                # Process items concurrently with limited parallelism
                semaphore = asyncio.Semaphore(min(5, len(batch.items)))
                
                async def process_item(item: BatchItem) -> ExtractionResult:
                    async with semaphore:
                        try:
                            # Simulate processing (in real implementation, this would call the actual extractor)
                            from .base_extractor import ExtractionResult, ExtractionStatus
                            
                            # Simulate processing time
                            processing_time = item.estimated_processing_time or 1.0
                            await asyncio.sleep(min(processing_time, 5.0))  # Cap simulation time
                            
                            result = ExtractionResult(
                                request_id=item.request.id,
                                status=ExtractionStatus.COMPLETED,
                                data=[{"simulated": True, "batch_id": batch.id}],
                                total_records=1,
                                processed_records=1,
                                processing_time_seconds=processing_time
                            )
                            
                            return result
                            
                        except Exception as e:
                            return ExtractionResult(
                                request_id=item.request.id,
                                status=ExtractionStatus.FAILED,
                                error_details={"error": str(e), "error_type": type(e).__name__}
                            )
                
                # Process all items
                tasks = [process_item(item) for item in batch.items]
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Count successes and failures
                for result in results:
                    if isinstance(result, Exception):
                        failed_count += 1
                        # Create error result
                        error_result = ExtractionResult(
                            request_id="unknown",
                            status=ExtractionStatus.FAILED,
                            error_details={"error": str(result)}
                        )
                        batch.results.append(error_result)
                    else:
                        batch.results.append(result)
                        if result.status == ExtractionStatus.COMPLETED:
                            successful_count += 1
                        else:
                            failed_count += 1
                
                # Update batch status
                if failed_count == 0:
                    batch.status = BatchStatus.COMPLETED
                elif successful_count == 0:
                    batch.status = BatchStatus.FAILED
                else:
                    batch.status = BatchStatus.PARTIAL
                
                batch.completed_at = datetime.utcnow()
                batch.processing_time_seconds = (
                    batch.completed_at - batch.started_at
                ).total_seconds()
                
                logger.info("Batch processing completed", 
                           batch_id=batch.id,
                           status=batch.status.value,
                           successful=successful_count,
                           failed=failed_count,
                           processing_time=batch.processing_time_seconds)
                
            except Exception as e:
                batch.status = BatchStatus.FAILED
                batch.error_details = {
                    "error": str(e),
                    "error_type": type(e).__name__
                }
                batch.completed_at = datetime.utcnow()
                
                logger.error("Batch processing failed", 
                            batch_id=batch.id,
                            error=str(e))
            
            finally:
                # Move batch to completed and update metrics
                if batch.id in self.active_batches:
                    del self.active_batches[batch.id]
                
                self.completed_batches.append(batch)
                await self._update_metrics(batch)
                
                # Keep only recent completed batches
                if len(self.completed_batches) > 1000:
                    self.completed_batches = self.completed_batches[-1000:]
    
    def _calculate_request_hash(self, request: ExtractionRequest) -> str:
        """Calculate hash for request deduplication"""
        import hashlib
        
        # Create hash based on source, target, and parameters
        hash_data = f"{request.source}:{request.target}:{str(sorted(request.parameters.items()))}"
        return hashlib.md5(hash_data.encode()).hexdigest()
    
    async def _update_metrics(self, batch: Batch):
        """Update processing metrics"""
        self.metrics.total_batches += 1
        self.metrics.total_items_processed += len(batch.items)
        
        if batch.status == BatchStatus.COMPLETED:
            self.metrics.completed_batches += 1
        elif batch.status == BatchStatus.FAILED:
            self.metrics.failed_batches += 1
        
        # Update averages
        if self.metrics.total_batches > 0:
            self.metrics.average_batch_size = (
                self.metrics.total_items_processed / self.metrics.total_batches
            )
            
            total_processing_time = sum(
                b.processing_time_seconds for b in self.completed_batches
            )
            self.metrics.average_processing_time = (
                total_processing_time / len(self.completed_batches)
            ) if self.completed_batches else 0.0
            
            # Calculate wait time (time from creation to processing start)
            total_wait_time = sum(
                (b.started_at - b.created_at).total_seconds() 
                for b in self.completed_batches
                if b.started_at
            )
            self.metrics.average_wait_time = (
                total_wait_time / len(self.completed_batches)
            ) if self.completed_batches else 0.0
            
            # Calculate throughput
            if self.metrics.average_processing_time > 0:
                self.metrics.throughput_items_per_second = (
                    self.metrics.average_batch_size / self.metrics.average_processing_time
                )
        
        # Calculate success rate
        if self.metrics.total_batches > 0:
            self.metrics.success_rate = (
                self.metrics.completed_batches / self.metrics.total_batches
            )
    
    def get_status(self) -> Dict[str, Any]:
        """Get current batch processor status"""
        return {
            "config": self.config.dict(),
            "metrics": self.metrics.dict(),
            "pending_items": len(self.pending_items),
            "active_batches": len(self.active_batches),
            "completed_batches": len(self.completed_batches),
            "resource_pressure": self.resource_monitor.get_resource_pressure(),
            "deduplication_cache_size": len(self.deduplication_cache)
        }
    
    def get_batch_status(self, batch_id: str) -> Optional[Dict[str, Any]]:
        """Get status of a specific batch"""
        # Check active batches
        if batch_id in self.active_batches:
            return self.active_batches[batch_id].dict()
        
        # Check completed batches
        for batch in self.completed_batches:
            if batch.id == batch_id:
                return batch.dict()
        
        return None
    
    async def cancel_batch(self, batch_id: str) -> bool:
        """Cancel an active batch"""
        if batch_id in self.active_batches:
            batch = self.active_batches[batch_id]
            batch.status = BatchStatus.CANCELLED
            batch.completed_at = datetime.utcnow()
            
            logger.info("Batch cancelled", batch_id=batch_id)
            return True
        
        return False
    
    def clear_cache(self):
        """Clear deduplication cache"""
        self.deduplication_cache.clear()
        logger.info("Deduplication cache cleared")
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on batch processor"""
        resource_pressure = self.resource_monitor.get_resource_pressure()
        
        # Determine health status
        if resource_pressure > 0.9:
            health_status = "critical"
        elif resource_pressure > 0.7:
            health_status = "warning"
        elif len(self.active_batches) >= self.config.max_concurrent_batches:
            health_status = "busy"
        else:
            health_status = "healthy"
        
        return {
            "status": health_status,
            "resource_pressure": resource_pressure,
            "queue_backlog": len(self.pending_items),
            "processing_capacity": f"{len(self.active_batches)}/{self.config.max_concurrent_batches}",
            "metrics": self.metrics.dict(),
            "recommendations": self._get_health_recommendations(health_status, resource_pressure)
        }
    
    def _get_health_recommendations(self, health_status: str, resource_pressure: float) -> List[str]:
        """Get health recommendations"""
        recommendations = []
        
        if health_status == "critical":
            recommendations.append("Critical resource pressure - consider scaling")
            recommendations.append("Reduce batch sizes or concurrent batches")
        
        elif health_status == "warning":
            recommendations.append("High resource usage - monitor closely")
            
        if len(self.pending_items) > self.config.max_batch_size * 3:
            recommendations.append("Large queue backlog - consider increasing processing capacity")
        
        if self.metrics.success_rate < 0.8:
            recommendations.append("Low success rate - investigate batch failures")
        
        return recommendations 