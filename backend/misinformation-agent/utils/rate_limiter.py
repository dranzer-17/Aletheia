"""
Rate limiter for API calls with exponential backoff and retry logic.
"""
import asyncio
import time
from typing import Any, Callable, TypeVar, Optional
from functools import wraps
from pathlib import Path
import sys

# Add backend root to path for logger import
BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
from logger import get_logger

logger = get_logger(__name__)

T = TypeVar('T')


class RateLimiter:
    """
    Rate limiter with exponential backoff for API calls.
    
    Implements a token bucket algorithm with retry logic for rate-limited APIs.
    """
    
    def __init__(
        self,
        max_requests: int = 5,
        time_window: float = 60.0,
        max_retries: int = 3,
        initial_backoff: float = 1.0,
        max_backoff: float = 60.0,
        backoff_multiplier: float = 2.0
    ):
        """
        Initialize rate limiter.
        
        Args:
            max_requests: Maximum number of requests allowed in time window
            time_window: Time window in seconds
            max_retries: Maximum number of retry attempts
            initial_backoff: Initial backoff delay in seconds
            max_backoff: Maximum backoff delay in seconds
            backoff_multiplier: Multiplier for exponential backoff
        """
        self.max_requests = max_requests
        self.time_window = time_window
        self.max_retries = max_retries
        self.initial_backoff = initial_backoff
        self.max_backoff = max_backoff
        self.backoff_multiplier = backoff_multiplier
        
        # Token bucket state
        self.tokens = max_requests
        self.last_update = time.time()
        self.lock = asyncio.Lock()
        
        logger.info(
            f"RateLimiter initialized: {max_requests} requests per {time_window}s, "
            f"max_retries={max_retries}"
        )
    
    async def _refill_tokens(self):
        """Refill tokens based on elapsed time."""
        now = time.time()
        elapsed = now - self.last_update
        
        # Calculate tokens to add based on elapsed time
        tokens_to_add = (elapsed / self.time_window) * self.max_requests
        self.tokens = min(self.max_requests, self.tokens + tokens_to_add)
        self.last_update = now
    
    async def acquire(self) -> bool:
        """
        Try to acquire a token for making a request.
        
        Returns:
            True if token acquired, False otherwise
        """
        async with self.lock:
            await self._refill_tokens()
            
            if self.tokens >= 1:
                self.tokens -= 1
                return True
            
            return False
    
    async def wait_for_token(self, timeout: Optional[float] = None) -> bool:
        """
        Wait until a token is available.
        
        Args:
            timeout: Maximum time to wait in seconds
        
        Returns:
            True if token acquired, False if timeout
        """
        start_time = time.time()
        
        while True:
            if await self.acquire():
                return True
            
            if timeout and (time.time() - start_time) >= timeout:
                logger.warning("Token acquisition timed out")
                return False
            
            # Wait a short time before trying again
            await asyncio.sleep(0.1)
    
    def calculate_backoff(self, attempt: int, suggested_delay: Optional[float] = None) -> float:
        """
        Calculate backoff delay with exponential backoff.
        
        Args:
            attempt: Current retry attempt number (0-indexed)
            suggested_delay: Suggested delay from API error response
        
        Returns:
            Backoff delay in seconds
        """
        if suggested_delay is not None:
            # Use API suggested delay if available
            delay = min(suggested_delay, self.max_backoff)
        else:
            # Calculate exponential backoff
            delay = min(
                self.initial_backoff * (self.backoff_multiplier ** attempt),
                self.max_backoff
            )
        
        return delay


async def with_rate_limit_retry(
    rate_limiter: RateLimiter,
    func: Callable[..., Any],
    *args,
    **kwargs
) -> T:
    """
    Execute a function with rate limiting and retry logic.
    
    Args:
        rate_limiter: RateLimiter instance
        func: Async function to execute
        *args: Positional arguments for func
        **kwargs: Keyword arguments for func
    
    Returns:
        Result from func
    
    Raises:
        Last exception if all retries exhausted
    """
    last_exception = None
    
    for attempt in range(rate_limiter.max_retries + 1):
        try:
            # Wait for rate limit token
            if not await rate_limiter.wait_for_token(timeout=rate_limiter.max_backoff):
                logger.warning(f"Rate limit token wait timeout on attempt {attempt + 1}")
                continue
            
            # Execute function
            logger.debug(f"Executing function (attempt {attempt + 1})")
            result = await func(*args, **kwargs)
            
            if attempt > 0:
                logger.info(f"Function succeeded after {attempt + 1} attempts")
            
            return result
            
        except Exception as e:
            last_exception = e
            error_msg = str(e)
            
            # Check if it's a rate limit error
            is_rate_limit = (
                "429" in error_msg or
                "quota" in error_msg.lower() or
                "rate limit" in error_msg.lower()
            )
            
            if is_rate_limit and attempt < rate_limiter.max_retries:
                # Try to extract suggested retry delay from error
                suggested_delay = None
                if "retry in" in error_msg.lower():
                    import re
                    match = re.search(r'retry in (\d+\.?\d*)', error_msg.lower())
                    if match:
                        suggested_delay = float(match.group(1))
                
                backoff = rate_limiter.calculate_backoff(attempt, suggested_delay)
                logger.warning(
                    f"Rate limit hit on attempt {attempt + 1}/{rate_limiter.max_retries + 1}. "
                    f"Retrying in {backoff:.2f}s... Error: {error_msg[:200]}"
                )
                
                await asyncio.sleep(backoff)
            else:
                # Not a rate limit error or no more retries
                logger.error(
                    f"Function failed on attempt {attempt + 1}: {error_msg[:200]}",
                    exc_info=not is_rate_limit
                )
                
                if attempt >= rate_limiter.max_retries:
                    logger.error(f"All {rate_limiter.max_retries + 1} attempts exhausted")
                    raise
                
                # For non-rate-limit errors, still retry with backoff
                if attempt < rate_limiter.max_retries:
                    backoff = rate_limiter.calculate_backoff(attempt)
                    logger.info(f"Retrying in {backoff:.2f}s...")
                    await asyncio.sleep(backoff)
    
    # Should never reach here, but just in case
    if last_exception:
        raise last_exception
    raise RuntimeError("Function execution failed with no exception recorded")


# Global rate limiter instance for Gemini API (free tier: 5 req/min)
gemini_rate_limiter = RateLimiter(
    max_requests=4,  # Use 4 instead of 5 to leave buffer
    time_window=60.0,  # 1 minute
    max_retries=3,
    initial_backoff=2.0,
    max_backoff=120.0,  # 2 minutes max
    backoff_multiplier=2.0
)

logger.info("Global Gemini rate limiter initialized")
