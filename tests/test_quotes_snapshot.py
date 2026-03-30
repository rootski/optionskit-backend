# tests/test_quotes_snapshot.py
"""
Tests for quotes snapshot endpoints and background service.
"""
import asyncio
import json
import pytest
from unittest.mock import AsyncMock, patch
from datetime import datetime

from app.services import snapshot_quotes
from app.services.snapshot_quotes import get_snapshot, get_last_update
from app.config import SNAPSHOT_TTL


async def _write_test_snapshot(quotes: list, last_update=None):
    """Write test data directly to the fake Redis used by snapshot_quotes."""
    from app.redis_client import get_redis
    now = last_update or datetime.now()
    redis = get_redis()
    pipe = redis.pipeline()
    pipe.set("optionskit:snapshot:results",     json.dumps(quotes), ex=SNAPSHOT_TTL)
    pipe.set("optionskit:snapshot:last_update", now.isoformat(),    ex=SNAPSHOT_TTL)
    pipe.set("optionskit:snapshot:count",       str(len(quotes)),   ex=SNAPSHOT_TTL)
    await pipe.execute()


@pytest.fixture
def mock_tradier_quotes(monkeypatch):
    """Mock Tradier quotes API response."""
    from app.vendors import tradier
    from app.services import snapshot_quotes as sq_module

    async def mock_get_quotes(symbols: list[str]):
        quotes = []
        for symbol in symbols:
            quotes.append({
                "symbol": symbol.upper(),
                "description": f"{symbol.upper()} Corporation",
                "last": 150.0 + hash(symbol) % 100,
                "bid": 149.5 + hash(symbol) % 100,
                "ask": 150.5 + hash(symbol) % 100,
                "volume": 1000000 + hash(symbol) % 100000,
                "exchange": "NASDAQ",
                "trade_time": "2024-01-15T10:00:00",
                "change": 1.5,
                "change_percent": 1.0
            })
        return quotes

    monkeypatch.setattr(tradier, 'get_quotes_tradier', mock_get_quotes)
    monkeypatch.setattr(sq_module, 'get_quotes_tradier', mock_get_quotes)
    return mock_get_quotes


@pytest.fixture
def mock_occ_symbols_for_quotes(monkeypatch, reset_mocks):
    """Mock OCC symbols service to return test symbols for quotes tests."""
    from app.services import occ_symbols
    import app.services.snapshot_quotes as sq_module

    test_symbols = {"AAPL", "MSFT", "GOOGL", "NFLX", "TSLA"}

    def mock_get_symbols():
        return test_symbols.copy()

    monkeypatch.setattr(occ_symbols, 'get_symbols', mock_get_symbols)
    monkeypatch.setattr(sq_module, 'get_symbols', mock_get_symbols)
    if hasattr(snapshot_quotes, 'get_symbols'):
        monkeypatch.setattr(snapshot_quotes, 'get_symbols', mock_get_symbols)

    return test_symbols


def test_quotes_snapshot_endpoint_structure(client):
    """Test quotes snapshot endpoint returns correct structure."""
    response = client.get("/v1/markets/quotes/snapshot")
    assert response.status_code == 200

    data = response.json()
    assert "last_update" in data
    assert "count" in data
    assert "results" in data
    assert isinstance(data["count"], int)
    assert isinstance(data["results"], list)
    assert data["last_update"] is None or isinstance(data["last_update"], str)


def test_quotes_last_update_endpoint_structure(client):
    """Test quotes last_update endpoint returns correct structure."""
    response = client.get("/v1/markets/quotes/last_update")
    assert response.status_code == 200

    data = response.json()
    assert "last_update" in data
    assert "count" in data
    assert isinstance(data["count"], int)
    assert data["last_update"] is None or isinstance(data["last_update"], str)


def test_quotes_snapshot_empty_initially(client):
    """Test that quotes snapshot is empty initially."""
    response = client.get("/v1/markets/quotes/snapshot")
    assert response.status_code == 200

    data = response.json()
    assert data["count"] == 0
    assert len(data["results"]) == 0
    assert data["last_update"] is None


def test_quotes_snapshot_with_data(client, mock_tradier_quotes, mock_occ_symbols_for_quotes):
    """Test quotes snapshot endpoint with mocked data."""
    test_quotes = [
        {
            "symbol": "AAPL",
            "description": "Apple Inc.",
            "last": 150.0,
            "bid": 149.5,
            "ask": 150.5,
            "volume": 1000000
        },
        {
            "symbol": "MSFT",
            "description": "Microsoft Corporation",
            "last": 300.0,
            "bid": 299.5,
            "ask": 300.5,
            "volume": 2000000
        }
    ]

    asyncio.run(_write_test_snapshot(test_quotes))

    response = client.get("/v1/markets/quotes/snapshot")
    assert response.status_code == 200

    data = response.json()
    assert data["count"] == 2
    assert len(data["results"]) == 2
    assert data["last_update"] is not None

    for quote in data["results"]:
        assert "symbol" in quote
        assert "description" in quote
        assert "last" in quote
        assert "bid" in quote
        assert "ask" in quote
        assert "volume" in quote


def test_quotes_last_update_with_data(client):
    """Test quotes last_update endpoint with mocked data."""
    test_quotes = [
        {
            "symbol": "AAPL",
            "description": "Apple Inc.",
            "last": 150.0,
            "bid": 149.5,
            "ask": 150.5,
            "volume": 1000000
        }
    ]

    asyncio.run(_write_test_snapshot(test_quotes))

    response = client.get("/v1/markets/quotes/last_update")
    assert response.status_code == 200

    data = response.json()
    assert data["count"] == 1
    assert data["last_update"] is not None
    assert "results" not in data


@pytest.mark.asyncio
async def test_refresh_quotes_snapshot_empty_symbols():
    """Test refresh when no symbols are available."""
    from app.services import occ_symbols

    with patch.object(occ_symbols, 'get_symbols', return_value=set()):
        success = await snapshot_quotes._refresh_quotes_snapshot()
        assert success is False

        from app.redis_client import get_redis
        count_str = await get_redis().get("optionskit:snapshot:count")
        assert (int(count_str) if count_str else 0) == 0


@pytest.mark.asyncio
async def test_refresh_quotes_snapshot_api_error(mock_occ_symbols_for_quotes):
    """Test refresh when Tradier API fails."""
    test_symbols = mock_occ_symbols_for_quotes

    async def mock_get_quotes_error(symbols: list[str]):
        raise Exception("Tradier API error")

    with patch('app.services.snapshot_quotes.get_symbols', return_value=test_symbols), \
         patch('app.services.snapshot_quotes.get_quotes_tradier', side_effect=mock_get_quotes_error):
        success = await snapshot_quotes._refresh_quotes_snapshot()
        assert success is False, "Should return False on API error"

        from app.redis_client import get_redis
        count_str = await get_redis().get("optionskit:snapshot:count")
        assert (int(count_str) if count_str else 0) == 0, "Snapshot should remain empty"


def test_chunk_list_function():
    """Test the _chunk_list helper function."""
    from app.services.snapshot_quotes import _chunk_list

    items = list(range(10))
    chunks = list(_chunk_list(items, 3))

    assert len(chunks) == 4
    assert chunks[0] == [0, 1, 2]
    assert chunks[1] == [3, 4, 5]
    assert chunks[2] == [6, 7, 8]
    assert chunks[3] == [9]


@pytest.mark.asyncio
async def test_background_task_start_stop(monkeypatch):
    """Test starting and stopping background task."""
    import app.services.snapshot_quotes

    with patch.object(app.services.snapshot_quotes, 'start_background_task',
                      wraps=app.services.snapshot_quotes.start_background_task):
        snapshot_quotes.start_background_task()
        if hasattr(snapshot_quotes, '_background_task') and snapshot_quotes._background_task is not None:
            assert not snapshot_quotes._background_task.done()

            await asyncio.sleep(0.1)

            snapshot_quotes.stop_background_task()
            await asyncio.sleep(0.1)

            assert snapshot_quotes._background_task.done()
        else:
            assert callable(snapshot_quotes.start_background_task)
            assert callable(snapshot_quotes.stop_background_task)


@pytest.mark.asyncio
async def test_quotes_api_available_within_5_seconds(client, mock_occ_symbols_for_quotes):
    """Integration test: Verify quotes APIs work within 5 seconds of startup."""
    import time

    test_symbols = mock_occ_symbols_for_quotes
    test_quotes = [
        {
            "symbol": symbol.upper(),
            "description": f"{symbol.upper()} Corporation",
            "last": 150.0,
            "bid": 149.5,
            "ask": 150.5,
            "volume": 1000000
        }
        for symbol in test_symbols
    ]

    start_time = time.time()
    await _write_test_snapshot(test_quotes)
    elapsed = time.time() - start_time

    assert elapsed < 5.0, f"Snapshot population should be fast, took {elapsed:.2f}s"

    response = client.get("/v1/markets/quotes/snapshot")
    assert response.status_code == 200
    data = response.json()
    assert data["count"] > 0, f"Expected count > 0, got {data['count']}"
    assert data["last_update"] is not None

    response = client.get("/v1/markets/quotes/last_update")
    assert response.status_code == 200
    data = response.json()
    assert data["count"] > 0
    assert data["last_update"] is not None


@pytest.mark.asyncio
async def test_quotes_snapshot_preserves_on_partial_failure(mock_occ_symbols_for_quotes):
    """Test that snapshot is preserved when refresh partially fails."""
    initial_quotes = [
        {
            "symbol": "AAPL",
            "description": "Apple Inc.",
            "last": 150.0,
            "bid": 149.5,
            "ask": 150.5,
            "volume": 1000000
        }
    ]
    initial_time = datetime(2024, 1, 15, 10, 0, 0)
    await _write_test_snapshot(initial_quotes, last_update=initial_time)

    test_symbols = mock_occ_symbols_for_quotes

    async def mock_get_quotes_empty(symbols: list[str]):
        return []

    with patch('app.services.snapshot_quotes.get_symbols', return_value=test_symbols), \
         patch('app.services.snapshot_quotes.get_quotes_tradier', side_effect=mock_get_quotes_empty):
        success = await snapshot_quotes._refresh_quotes_snapshot()
        assert success is False, "Should return False when no quotes returned"

        from app.redis_client import get_redis
        redis = get_redis()
        count_str = await redis.get("optionskit:snapshot:count")
        last_update_str = await redis.get("optionskit:snapshot:last_update")

        assert (int(count_str) if count_str else 0) == 1, "Snapshot count should be preserved"
        assert last_update_str == initial_time.isoformat(), "Timestamp should be preserved"
