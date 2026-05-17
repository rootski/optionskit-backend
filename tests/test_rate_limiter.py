# tests/test_rate_limiter.py
"""
Unit tests for the sliding-window rate limiter.
Uses time.time() mocking to avoid real sleeps.
"""
import asyncio
import time
import pytest
from unittest.mock import patch

from app.vendors.rate_limiter import RateLimiter


# ---------------------------------------------------------------------------
# get_stats
# ---------------------------------------------------------------------------

def test_get_stats_initial():
    rl = RateLimiter(max_requests=120, window_seconds=60)
    stats = rl.get_stats()
    assert stats["max_requests"] == 120
    assert stats["requests_in_window"] == 0
    assert stats["available"] == 120
    assert stats["window_seconds"] == 60


def test_get_stats_after_requests():
    rl = RateLimiter(max_requests=10, window_seconds=60)
    now = time.time()
    rl.request_times.extend([now, now, now])
    stats = rl.get_stats()
    assert stats["requests_in_window"] == 3
    assert stats["available"] == 7


def test_get_stats_expires_old_entries():
    rl = RateLimiter(max_requests=10, window_seconds=60)
    old = time.time() - 120  # 2 minutes ago — outside the window
    rl.request_times.append(old)
    stats = rl.get_stats()
    assert stats["requests_in_window"] == 0
    assert stats["available"] == 10


def test_get_stats_available_never_negative():
    rl = RateLimiter(max_requests=2, window_seconds=60)
    now = time.time()
    rl.request_times.extend([now, now, now])  # 3 > max
    stats = rl.get_stats()
    assert stats["available"] == 0


# ---------------------------------------------------------------------------
# update_from_headers
# ---------------------------------------------------------------------------

def test_update_from_headers_updates_max():
    rl = RateLimiter(max_requests=60)
    rl.update_from_headers({"X-Ratelimit-Allowed": "120"})
    assert rl.max_requests == 120


def test_update_from_headers_no_change_if_same():
    rl = RateLimiter(max_requests=120)
    rl.update_from_headers({"X-Ratelimit-Allowed": "120"})
    assert rl.max_requests == 120


def test_update_from_headers_bad_allowed_value():
    rl = RateLimiter(max_requests=120)
    rl.update_from_headers({"X-Ratelimit-Allowed": "not-a-number"})
    assert rl.max_requests == 120  # unchanged


def test_update_from_headers_missing_keys():
    rl = RateLimiter(max_requests=120)
    rl.update_from_headers({})  # should not raise
    assert rl.max_requests == 120


def test_update_from_headers_none_values():
    rl = RateLimiter(max_requests=120)
    rl.update_from_headers({"X-Ratelimit-Allowed": None})
    assert rl.max_requests == 120


# ---------------------------------------------------------------------------
# acquire — under limit
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_acquire_under_limit_does_not_sleep():
    rl = RateLimiter(max_requests=10, window_seconds=60)
    sleep_called = False

    async def fake_sleep(t):
        nonlocal sleep_called
        sleep_called = True

    with patch("app.vendors.rate_limiter.asyncio.sleep", fake_sleep):
        await rl.acquire()

    assert not sleep_called
    assert len(rl.request_times) == 1


@pytest.mark.asyncio
async def test_acquire_records_timestamp():
    rl = RateLimiter(max_requests=10, window_seconds=60)
    before = time.time()
    await rl.acquire()
    after = time.time()
    assert len(rl.request_times) == 1
    assert before <= rl.request_times[0] <= after


@pytest.mark.asyncio
async def test_acquire_multiple_under_limit():
    rl = RateLimiter(max_requests=10, window_seconds=60)
    for _ in range(5):
        await rl.acquire()
    assert len(rl.request_times) == 5


# ---------------------------------------------------------------------------
# acquire — at limit (triggers sleep)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_acquire_at_limit_sleeps():
    rl = RateLimiter(max_requests=3, window_seconds=60)
    now = time.time()
    # Pre-fill with 3 recent requests
    rl.request_times.extend([now - 10, now - 5, now - 1])

    sleep_durations = []

    async def fake_sleep(t):
        sleep_durations.append(t)
        # Simulate time passing: expire old entries so acquire doesn't loop
        rl.request_times.clear()

    with patch("app.vendors.rate_limiter.asyncio.sleep", fake_sleep):
        await rl.acquire()

    assert len(sleep_durations) == 1
    assert sleep_durations[0] > 0


@pytest.mark.asyncio
async def test_acquire_at_limit_sleep_duration_reasonable():
    """Sleep duration should be ~(window - age_of_oldest) + buffer."""
    rl = RateLimiter(max_requests=2, window_seconds=60)
    now = time.time()
    oldest = now - 30  # 30 seconds ago → should wait ~30s + 0.1
    rl.request_times.extend([oldest, now - 1])

    sleep_durations = []

    async def fake_sleep(t):
        sleep_durations.append(t)
        rl.request_times.clear()

    with patch("app.vendors.rate_limiter.asyncio.sleep", fake_sleep):
        with patch("app.vendors.rate_limiter.time.time", return_value=now):
            await rl.acquire()

    assert len(sleep_durations) == 1
    assert 29.0 < sleep_durations[0] < 31.0


# ---------------------------------------------------------------------------
# acquire — expired entries pruned
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_acquire_prunes_expired_entries():
    rl = RateLimiter(max_requests=3, window_seconds=60)
    old = time.time() - 120  # 2 minutes ago
    rl.request_times.extend([old, old, old])  # would be at limit if not expired

    sleep_called = False

    async def fake_sleep(t):
        nonlocal sleep_called
        sleep_called = True

    with patch("app.vendors.rate_limiter.asyncio.sleep", fake_sleep):
        await rl.acquire()

    assert not sleep_called  # old entries pruned, not at limit


# ---------------------------------------------------------------------------
# acquire — concurrency (lock prevents double-counting)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_acquire_concurrent_respects_limit():
    """Concurrent acquires should each record exactly one timestamp."""
    rl = RateLimiter(max_requests=100, window_seconds=60)
    await asyncio.gather(*[rl.acquire() for _ in range(10)])
    assert len(rl.request_times) == 10
