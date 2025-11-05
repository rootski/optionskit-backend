"""
Rate limiter for Tradier API to prevent exceeding rate limits.
Based on: https://docs.tradier.com/docs/rate-limiting

Market Data endpoints:
- Production: 120 requests per minute
- Sandbox: 60 requests per minute
"""
import asyncio
import time
from collections import deque
from typing import Optional


class RateLimiter:
    """
    Sliding window rate limiter that respects Tradier's per-minute limits.
    Uses a sliding window to track requests within the last 60 seconds.
    """
    
    def __init__(self, max_requests: int = 120, window_seconds: int = 60):
        """
        Initialize rate limiter.
        
        Args:
            max_requests: Maximum requests allowed per window (120 for production, 60 for sandbox)
            window_seconds: Time window in seconds (60 for Tradier's 1-minute intervals)
        """
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.request_times: deque = deque()
        self.lock = asyncio.Lock()
    
    async def acquire(self) -> None:
        """
        Wait if necessary to ensure we don't exceed the rate limit.
        Should be called before making a request.
        """
        async with self.lock:
            now = time.time()
            
            # Remove requests older than the window
            while self.request_times and self.request_times[0] < now - self.window_seconds:
                self.request_times.popleft()
            
            # If we're at the limit, wait until the oldest request expires
            if len(self.request_times) >= self.max_requests:
                oldest_time = self.request_times[0]
                wait_time = self.window_seconds - (now - oldest_time) + 0.1  # Add small buffer
                if wait_time > 0:
                    await asyncio.sleep(wait_time)
                    # Clean up expired requests again after waiting
                    now = time.time()
                    while self.request_times and self.request_times[0] < now - self.window_seconds:
                        self.request_times.popleft()
            
            # Record this request
            self.request_times.append(time.time())
    
    def update_from_headers(self, headers: dict) -> None:
        """
        Update rate limiter state based on Tradier response headers.
        
        Headers:
        - X-Ratelimit-Allowed: Maximum requests allowed
        - X-Ratelimit-Used: Requests used in current window
        - X-Ratelimit-Available: Requests remaining
        - X-Ratelimit-Expiry: Expiry timestamp (milliseconds)
        """
        allowed = headers.get("X-Ratelimit-Allowed")
        used = headers.get("X-Ratelimit-Used")
        available = headers.get("X-Ratelimit-Available")
        expiry = headers.get("X-Ratelimit-Expiry")
        
        if allowed:
            try:
                # Update max_requests if Tradier reports a different limit
                new_max = int(allowed)
                if new_max != self.max_requests:
                    self.max_requests = new_max
            except (ValueError, TypeError):
                pass
        
        if available:
            try:
                available_count = int(available)
                # If we're close to the limit, adjust our tracking
                if available_count < 5:  # Less than 5 requests remaining
                    # Be more conservative - wait a bit longer
                    pass
            except (ValueError, TypeError):
                pass
    
    def get_stats(self) -> dict:
        """Get current rate limiter statistics."""
        now = time.time()
        # Clean up expired requests
        while self.request_times and self.request_times[0] < now - self.window_seconds:
            self.request_times.popleft()
        
        return {
            "max_requests": self.max_requests,
            "requests_in_window": len(self.request_times),
            "available": max(0, self.max_requests - len(self.request_times)),
            "window_seconds": self.window_seconds
        }


