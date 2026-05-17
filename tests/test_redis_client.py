# tests/test_redis_client.py
"""
Unit tests for app/redis_client.py.

Note: conftest.py globally patches init_redis and close_redis as AsyncMocks
to prevent real connections during the test suite. Tests that exercise the
real implementations temporarily stop those specific patches.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import app.redis_client as redis_client_module
from app.redis_client import get_redis


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def real_redis_funcs():
    """
    Stop the conftest patches for init_redis, close_redis, and _redis so we
    can exercise the actual implementations. Restores them after the test.
    """
    import tests.conftest as conftest_mod

    # Indices match the order in conftest._patchers.extend([...])
    # patcher9 (_redis), patcher10 (init_redis), patcher11 (close_redis)
    patcher_redis = conftest_mod._patchers[8]
    patcher_init  = conftest_mod._patchers[9]
    patcher_close = conftest_mod._patchers[10]

    patcher_redis.stop()
    patcher_init.stop()
    patcher_close.stop()

    yield

    patcher_redis.start()
    patcher_init.start()
    patcher_close.start()


# ---------------------------------------------------------------------------
# get_redis — no patchers involved
# ---------------------------------------------------------------------------

def test_get_redis_raises_before_init():
    """get_redis() should raise when _redis is None."""
    original = redis_client_module._redis
    redis_client_module._redis = None
    try:
        with pytest.raises(RuntimeError, match="Redis not initialized"):
            get_redis()
    finally:
        redis_client_module._redis = original


def test_get_redis_returns_client_when_set():
    """get_redis() should return the current client."""
    mock_client = MagicMock()
    original = redis_client_module._redis
    redis_client_module._redis = mock_client
    try:
        assert get_redis() is mock_client
    finally:
        redis_client_module._redis = original


# ---------------------------------------------------------------------------
# init_redis — real implementation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_init_redis_calls_ping(real_redis_funcs):
    mock_client = AsyncMock()
    with patch("app.redis_client.aioredis.from_url", return_value=mock_client):
        await redis_client_module.init_redis()
    mock_client.ping.assert_called_once()


@pytest.mark.asyncio
async def test_init_redis_sets_global(real_redis_funcs):
    mock_client = AsyncMock()
    with patch("app.redis_client.aioredis.from_url", return_value=mock_client):
        await redis_client_module.init_redis()
    assert redis_client_module._redis is mock_client


@pytest.mark.asyncio
async def test_init_redis_raises_on_ping_failure(real_redis_funcs):
    mock_client = AsyncMock()
    mock_client.ping.side_effect = ConnectionError("Redis unreachable")
    with patch("app.redis_client.aioredis.from_url", return_value=mock_client):
        with pytest.raises(ConnectionError, match="Redis unreachable"):
            await redis_client_module.init_redis()


# ---------------------------------------------------------------------------
# close_redis — real implementation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_close_redis_calls_aclose(real_redis_funcs):
    mock_client = AsyncMock()
    redis_client_module._redis = mock_client
    await redis_client_module.close_redis()
    mock_client.aclose.assert_called_once()


@pytest.mark.asyncio
async def test_close_redis_sets_global_to_none(real_redis_funcs):
    mock_client = AsyncMock()
    redis_client_module._redis = mock_client
    await redis_client_module.close_redis()
    assert redis_client_module._redis is None


@pytest.mark.asyncio
async def test_close_redis_noop_when_not_initialized(real_redis_funcs):
    redis_client_module._redis = None
    await redis_client_module.close_redis()  # should not raise


@pytest.mark.asyncio
async def test_close_redis_idempotent(real_redis_funcs):
    mock_client = AsyncMock()
    redis_client_module._redis = mock_client
    await redis_client_module.close_redis()
    await redis_client_module.close_redis()  # second call — _redis is already None
