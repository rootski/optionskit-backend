# app/redis_client.py
import logging
from typing import Optional
import redis.asyncio as aioredis
from .config import REDIS_URL

logger = logging.getLogger(__name__)

_redis: Optional[aioredis.Redis] = None


async def init_redis() -> None:
    """
    Initialize the Redis connection pool.
    Raises on failure — Redis is a required dependency.
    Called from the FastAPI lifespan context.
    """
    global _redis
    _redis = aioredis.from_url(
        REDIS_URL,
        encoding="utf-8",
        decode_responses=True,
        socket_connect_timeout=5,
        socket_timeout=5,
    )
    await _redis.ping()
    logger.info(f"Redis connected: {REDIS_URL}")


async def close_redis() -> None:
    """Close the Redis connection pool. Called from lifespan shutdown."""
    global _redis
    if _redis:
        await _redis.aclose()
        _redis = None
        logger.info("Redis connection closed")


def get_redis() -> aioredis.Redis:
    """Return the active Redis client. Raises if not initialized."""
    if _redis is None:
        raise RuntimeError("Redis not initialized. Call init_redis() first.")
    return _redis
