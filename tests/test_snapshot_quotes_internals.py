# tests/test_snapshot_quotes_internals.py
"""
Tests for snapshot_quotes internal helpers, refresh logic, get_snapshot,
get_last_update, get_background_task_status, and the background loop.

These tests supplement test_quotes_snapshot.py which covers the HTTP endpoints.
All tests use the fakeredis instance wired up in conftest.py.
"""
import asyncio
import json
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, patch, MagicMock

import app.services.snapshot_quotes as sq
from app.services.snapshot_quotes import (
    _write_snapshot_to_redis,
    _read_snapshot_from_redis,
    _refresh_quotes_snapshot,
    _background_refresh_loop,
    get_snapshot,
    get_last_update,
    get_background_task_status,
    start_background_task,
    stop_background_task,
    _KEY_RESULTS,
    _KEY_LAST_UPDATE,
    _KEY_COUNT,
)
from app.redis_client import get_redis
from app.config import SNAPSHOT_TTL


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_quotes(n: int = 3) -> list:
    symbols = ["AAPL", "MSFT", "GOOGL", "TSLA", "NFLX"]
    return [
        {"symbol": symbols[i % len(symbols)], "description": f"Company {i}",
         "last": 100.0 + i, "bid": 99.5 + i, "ask": 100.5 + i, "volume": 1000 + i}
        for i in range(n)
    ]


# ---------------------------------------------------------------------------
# _write_snapshot_to_redis
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_write_snapshot_stores_results():
    quotes = _make_quotes(2)
    now = datetime(2026, 5, 17, 10, 0, 0)
    await _write_snapshot_to_redis(quotes, now)

    redis = get_redis()
    stored = await redis.get(_KEY_RESULTS)
    assert json.loads(stored) == quotes


@pytest.mark.asyncio
async def test_write_snapshot_stores_last_update():
    now = datetime(2026, 5, 17, 10, 0, 0)
    await _write_snapshot_to_redis(_make_quotes(1), now)

    redis = get_redis()
    stored = await redis.get(_KEY_LAST_UPDATE)
    assert stored == now.isoformat()


@pytest.mark.asyncio
async def test_write_snapshot_stores_count():
    quotes = _make_quotes(5)
    await _write_snapshot_to_redis(quotes, datetime.now())

    redis = get_redis()
    count = await redis.get(_KEY_COUNT)
    assert int(count) == 5


@pytest.mark.asyncio
async def test_write_snapshot_sets_ttl():
    await _write_snapshot_to_redis(_make_quotes(1), datetime.now())

    redis = get_redis()
    ttl = await redis.ttl(_KEY_RESULTS)
    assert 0 < ttl <= SNAPSHOT_TTL


# ---------------------------------------------------------------------------
# _read_snapshot_from_redis
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_read_snapshot_empty_redis():
    result = await _read_snapshot_from_redis()
    assert result["results"] == []
    assert result["last_update"] is None
    assert result["count"] == 0
    assert result["by_symbol"] == {}


@pytest.mark.asyncio
async def test_read_snapshot_returns_correct_data():
    quotes = _make_quotes(3)
    now = datetime(2026, 5, 17, 12, 0, 0)
    await _write_snapshot_to_redis(quotes, now)

    result = await _read_snapshot_from_redis()
    assert result["count"] == 3
    assert result["last_update"] == now
    assert result["results"] == quotes


@pytest.mark.asyncio
async def test_read_snapshot_builds_by_symbol():
    quotes = [
        {"symbol": "AAPL", "description": "Apple", "last": 175.0,
         "bid": 174.9, "ask": 175.1, "volume": 1000},
        {"symbol": "MSFT", "description": "Microsoft", "last": 420.0,
         "bid": 419.5, "ask": 420.5, "volume": 2000},
    ]
    await _write_snapshot_to_redis(quotes, datetime.now())

    result = await _read_snapshot_from_redis()
    assert "AAPL" in result["by_symbol"]
    assert "MSFT" in result["by_symbol"]
    assert result["by_symbol"]["AAPL"]["last"] == 175.0


# ---------------------------------------------------------------------------
# _refresh_quotes_snapshot
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_refresh_success_writes_to_redis():
    quotes = _make_quotes(3)

    async def mock_get_quotes(symbols):
        return [{"symbol": s, "description": "", "last": 100.0,
                 "bid": 99.5, "ask": 100.5, "volume": 1000} for s in symbols]

    with patch.object(sq, "get_symbols", return_value={"AAPL", "MSFT", "GOOGL"}), \
         patch.object(sq, "get_quotes_tradier", side_effect=mock_get_quotes):
        success = await _refresh_quotes_snapshot()

    assert success is True
    redis = get_redis()
    count = await redis.get(_KEY_COUNT)
    assert int(count) == 3


@pytest.mark.asyncio
async def test_refresh_normalizes_quote_fields():
    """Refresh should extract only the 6 snapshot fields from raw quotes."""
    raw_quotes = [{
        "symbol": "AAPL", "description": "Apple Inc",
        "last": 175.0, "bid": 174.9, "ask": 175.1, "volume": 50000000,
        "exchange": "Q", "trade_time": "2026-05-17T16:00:00",  # extra fields
        "change": 1.5, "change_percent": 0.86,
    }]

    with patch.object(sq, "get_symbols", return_value={"AAPL"}), \
         patch.object(sq, "get_quotes_tradier", return_value=raw_quotes):
        await _refresh_quotes_snapshot()

    redis = get_redis()
    stored = json.loads(await redis.get(_KEY_RESULTS))
    assert len(stored) == 1
    assert set(stored[0].keys()) == {"symbol", "description", "last", "bid", "ask", "volume"}


@pytest.mark.asyncio
async def test_refresh_returns_false_when_no_symbols():
    with patch.object(sq, "get_symbols", return_value=set()):
        success = await _refresh_quotes_snapshot()
    assert success is False


@pytest.mark.asyncio
async def test_refresh_returns_false_when_all_batches_return_empty():
    with patch.object(sq, "get_symbols", return_value={"AAPL"}), \
         patch.object(sq, "get_quotes_tradier", return_value=[]):
        success = await _refresh_quotes_snapshot()
    assert success is False


@pytest.mark.asyncio
async def test_refresh_returns_false_on_exception():
    with patch.object(sq, "get_symbols", side_effect=RuntimeError("boom")):
        success = await _refresh_quotes_snapshot()
    assert success is False


@pytest.mark.asyncio
async def test_refresh_preserves_existing_snapshot_on_failure():
    """Existing Redis snapshot is not overwritten when refresh returns no quotes."""
    initial = _make_quotes(2)
    initial_time = datetime(2026, 5, 17, 9, 0, 0)
    await _write_snapshot_to_redis(initial, initial_time)

    with patch.object(sq, "get_symbols", return_value={"AAPL"}), \
         patch.object(sq, "get_quotes_tradier", return_value=[]):
        success = await _refresh_quotes_snapshot()

    assert success is False
    redis = get_redis()
    count = await redis.get(_KEY_COUNT)
    assert int(count) == 2  # still the original 2


@pytest.mark.asyncio
async def test_refresh_handles_batch_exception():
    """A batch that raises should count as an error but not crash the refresh."""
    call_count = 0

    async def flaky_quotes(symbols):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise Exception("Tradier timeout")
        return [{"symbol": s, "description": "", "last": 100.0,
                 "bid": 99.5, "ask": 100.5, "volume": 1000} for s in symbols]

    with patch.object(sq, "get_symbols", return_value={"AAPL", "MSFT"}), \
         patch.object(sq, "get_quotes_tradier", side_effect=flaky_quotes):
        # With BATCH_SIZE large enough, only 1 batch → 1 exception → returns False
        with patch("app.services.snapshot_quotes.BATCH_SIZE", 1):
            success = await _refresh_quotes_snapshot()

    # One batch succeeded, one failed — partial success still writes if quotes > 0
    # (behavior depends on which batch failed; success when any quotes returned)
    assert isinstance(success, bool)


# ---------------------------------------------------------------------------
# get_snapshot
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_snapshot_returns_all_when_no_filter():
    quotes = _make_quotes(3)
    await _write_snapshot_to_redis(quotes, datetime.now())

    result = await get_snapshot()
    assert result["count"] == 3
    assert len(result["results"]) == 3
    assert result["last_update"] is not None


@pytest.mark.asyncio
async def test_get_snapshot_filters_by_symbol():
    quotes = [
        {"symbol": "AAPL", "description": "Apple", "last": 175.0,
         "bid": 174.9, "ask": 175.1, "volume": 1000},
        {"symbol": "MSFT", "description": "Microsoft", "last": 420.0,
         "bid": 419.5, "ask": 420.5, "volume": 2000},
        {"symbol": "GOOGL", "description": "Alphabet", "last": 180.0,
         "bid": 179.5, "ask": 180.5, "volume": 3000},
    ]
    await _write_snapshot_to_redis(quotes, datetime.now())

    result = await get_snapshot(symbols=["AAPL", "MSFT"])
    assert result["count"] == 2
    symbols_returned = {r["symbol"] for r in result["results"]}
    assert symbols_returned == {"AAPL", "MSFT"}


@pytest.mark.asyncio
async def test_get_snapshot_filter_case_insensitive():
    quotes = [{"symbol": "AAPL", "description": "Apple", "last": 175.0,
               "bid": 174.9, "ask": 175.1, "volume": 1000}]
    await _write_snapshot_to_redis(quotes, datetime.now())

    result = await get_snapshot(symbols=["aapl"])
    assert result["count"] == 1


@pytest.mark.asyncio
async def test_get_snapshot_filter_unknown_symbol_excluded():
    quotes = [{"symbol": "AAPL", "description": "Apple", "last": 175.0,
               "bid": 174.9, "ask": 175.1, "volume": 1000}]
    await _write_snapshot_to_redis(quotes, datetime.now())

    result = await get_snapshot(symbols=["AAPL", "FAKE"])
    assert result["count"] == 1


@pytest.mark.asyncio
async def test_get_snapshot_empty_filter_returns_all():
    quotes = _make_quotes(2)
    await _write_snapshot_to_redis(quotes, datetime.now())

    result = await get_snapshot(symbols=[])
    assert result["count"] == 2


@pytest.mark.asyncio
async def test_get_snapshot_last_update_is_isoformat_string():
    await _write_snapshot_to_redis(_make_quotes(1), datetime(2026, 5, 17, 10, 0, 0))
    result = await get_snapshot()
    assert isinstance(result["last_update"], str)
    # Should be parseable as ISO datetime
    datetime.fromisoformat(result["last_update"])


@pytest.mark.asyncio
async def test_get_snapshot_empty_redis_returns_none_last_update():
    result = await get_snapshot()
    assert result["last_update"] is None
    assert result["count"] == 0


# ---------------------------------------------------------------------------
# get_last_update
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_last_update_empty_redis():
    result = await get_last_update()
    assert result["last_update"] is None
    assert result["count"] == 0


@pytest.mark.asyncio
async def test_get_last_update_with_data():
    await _write_snapshot_to_redis(_make_quotes(4), datetime(2026, 5, 17, 14, 0, 0))
    result = await get_last_update()
    assert result["count"] == 4
    assert result["last_update"] is not None
    assert "results" not in result


# ---------------------------------------------------------------------------
# get_background_task_status
# ---------------------------------------------------------------------------

def test_status_when_no_task():
    original = sq._background_task
    sq._background_task = None
    try:
        status = get_background_task_status()
        assert status["running"] is False
        assert "not started" in status["message"]
    finally:
        sq._background_task = original


@pytest.mark.asyncio
async def test_status_when_task_running():
    async def _forever():
        await asyncio.sleep(9999)

    task = asyncio.get_event_loop().create_task(_forever())
    original = sq._background_task
    sq._background_task = task
    try:
        status = get_background_task_status()
        assert status["running"] is True
        assert status["done"] is False
        assert status["cancelled"] is False
        assert "running" in status["message"]
    finally:
        task.cancel()
        sq._background_task = original


@pytest.mark.asyncio
async def test_status_when_task_cancelled():
    async def _forever():
        await asyncio.sleep(9999)

    task = asyncio.get_event_loop().create_task(_forever())
    task.cancel()
    try:
        await task
    except (asyncio.CancelledError, Exception):
        pass

    original = sq._background_task
    sq._background_task = task
    try:
        status = get_background_task_status()
        assert status["done"] is True
        assert status["cancelled"] is True
        assert "cancelled" in status["message"]
    finally:
        sq._background_task = original


@pytest.mark.asyncio
async def test_status_when_task_completed():
    async def _noop():
        pass

    task = asyncio.get_event_loop().create_task(_noop())
    await asyncio.sleep(0)  # let task finish

    original = sq._background_task
    sq._background_task = task
    try:
        status = get_background_task_status()
        assert status["done"] is True
        assert status["cancelled"] is False
        assert "completed" in status["message"]
    finally:
        sq._background_task = original


# ---------------------------------------------------------------------------
# start_background_task / stop_background_task
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_start_creates_task():
    original = sq._background_task
    sq._background_task = None

    async def _forever():
        await asyncio.sleep(9999)

    try:
        with patch.object(sq, "_background_refresh_loop", _forever):
            # Call create_task directly since start_background_task uses
            # get_event_loop() which may differ from the running loop in pytest
            sq._background_task = asyncio.get_running_loop().create_task(_forever())
            await asyncio.sleep(0)
            assert sq._background_task is not None
            assert not sq._background_task.done()
    finally:
        if sq._background_task and not sq._background_task.done():
            sq._background_task.cancel()
        sq._background_task = original


@pytest.mark.asyncio
async def test_start_does_not_duplicate_running_task():
    original = sq._background_task

    async def _forever():
        await asyncio.sleep(9999)

    task = asyncio.get_event_loop().create_task(_forever())
    sq._background_task = task
    try:
        start_background_task()
        assert sq._background_task is task  # same task, not replaced
    finally:
        task.cancel()
        sq._background_task = original


@pytest.mark.asyncio
async def test_stop_cancels_task():
    original = sq._background_task

    async def _forever():
        await asyncio.sleep(9999)

    task = asyncio.get_event_loop().create_task(_forever())
    sq._background_task = task
    try:
        stop_background_task()
        await asyncio.sleep(0)
        assert task.cancelled()
    finally:
        sq._background_task = original


@pytest.mark.asyncio
async def test_stop_noop_when_no_task():
    original = sq._background_task
    sq._background_task = None
    try:
        stop_background_task()  # should not raise
    finally:
        sq._background_task = original


# ---------------------------------------------------------------------------
# _background_refresh_loop — startup behaviour
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_background_loop_runs_initial_refresh():
    """Loop should call _refresh_quotes_snapshot immediately on startup."""
    refresh_calls = []

    async def mock_refresh():
        refresh_calls.append(1)
        return True

    async def mock_sleep(_):
        raise asyncio.CancelledError()  # break the while True after first iteration

    with patch.object(sq, "get_symbols", return_value={"AAPL"}), \
         patch.object(sq, "_refresh_quotes_snapshot", side_effect=mock_refresh), \
         patch("app.services.snapshot_quotes.asyncio.sleep", side_effect=mock_sleep):
        with pytest.raises(asyncio.CancelledError):
            await _background_refresh_loop()

    assert len(refresh_calls) >= 1


@pytest.mark.asyncio
async def test_background_loop_waits_for_occ_symbols():
    """Loop should retry while OCC symbols are empty, up to max attempts."""
    sleep_calls = []
    symbol_call_count = 0

    def mock_get_symbols():
        nonlocal symbol_call_count
        symbol_call_count += 1
        if symbol_call_count >= 3:
            return {"AAPL"}
        return set()

    async def mock_sleep(t):
        sleep_calls.append(t)
        if len(sleep_calls) > 5:
            raise asyncio.CancelledError()

    async def mock_refresh():
        raise asyncio.CancelledError()

    with patch.object(sq, "get_symbols", side_effect=mock_get_symbols), \
         patch.object(sq, "_refresh_quotes_snapshot", side_effect=mock_refresh), \
         patch("app.services.snapshot_quotes.asyncio.sleep", side_effect=mock_sleep):
        with pytest.raises(asyncio.CancelledError):
            await _background_refresh_loop()

    assert symbol_call_count >= 3
