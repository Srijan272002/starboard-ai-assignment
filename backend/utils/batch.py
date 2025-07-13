from typing import TypeVar, List, Callable, Any, Awaitable
import asyncio
from datetime import datetime
from backend.utils.logger import setup_logger

logger = setup_logger("batch")

T = TypeVar('T')
R = TypeVar('R')

class BatchProcessor:
    def __init__(
        self,
        batch_size: int = 10,
        max_concurrent: int = 5,
        timeout: float = 30.0
    ):
        self.batch_size = batch_size
        self.max_concurrent = max_concurrent
        self.timeout = timeout
        self.semaphore = asyncio.Semaphore(max_concurrent)

    async def process_batch(
        self,
        items: List[T],
        processor: Callable[[T], Awaitable[R]]
    ) -> List[R]:
        """
        Process items in batches with concurrency control
        """
        results = []
        batches = [
            items[i:i + self.batch_size]
            for i in range(0, len(items), self.batch_size)
        ]

        async def process_item(item: T) -> R:
            async with self.semaphore:
                try:
                    return await asyncio.wait_for(
                        processor(item),
                        timeout=self.timeout
                    )
                except asyncio.TimeoutError:
                    logger.error(f"Processing timeout for item: {item}")
                    raise
                except Exception as e:
                    logger.error(f"Processing error for item {item}: {str(e)}")
                    raise

        for batch in batches:
            try:
                batch_results = await asyncio.gather(
                    *[process_item(item) for item in batch],
                    return_exceptions=True
                )
                
                # Filter out exceptions and log them
                for i, result in enumerate(batch_results):
                    if isinstance(result, Exception):
                        logger.error(f"Batch item {i} failed: {str(result)}")
                    else:
                        results.append(result)
                        
            except Exception as e:
                logger.error(f"Batch processing error: {str(e)}")
                continue

        return results

# Global batch processor instance
batch_processor = BatchProcessor() 