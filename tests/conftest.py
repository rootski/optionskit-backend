# tests/conftest.py
"""
Shared fixtures for all tests.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient
from datetime import datetime

from app.main import app


@pytest.fixture
def client():
    """Create a test client for the API."""
    return TestClient(app)


@pytest.fixture
def mock_occ_symbols(monkeypatch):
    """Mock OCC symbols service to return test symbols."""
    from app.services import occ_symbols
    
    test_symbols = {"AAPL", "MSFT", "GOOGL", "NFLX", "TSLA"}
    
    def mock_get_symbols():
        return test_symbols.copy()
    
    def mock_get_symbol_count():
        return len(test_symbols)
    
    def mock_get_last_update():
        return datetime(2024, 1, 15, 2, 0, 0)
    
    monkeypatch.setattr(occ_symbols, 'get_symbols', mock_get_symbols)
    monkeypatch.setattr(occ_symbols, 'get_symbol_count', mock_get_symbol_count)
    monkeypatch.setattr(occ_symbols, 'get_last_update', mock_get_last_update)
    
    return test_symbols


@pytest.fixture
def mock_tradier_expirations(monkeypatch):
    """Mock Tradier expirations API response."""
    from app.vendors import tradier
    
    async def mock_get_expirations(symbol: str):
        return {
            "symbol": symbol.upper(),
            "expirations": ["2024-01-19", "2024-01-26", "2024-02-02"],
            "expiration_data": [
                {
                    "date": "2024-01-19",
                    "strikes": [100.0, 105.0, 110.0, 115.0, 120.0]
                },
                {
                    "date": "2024-01-26",
                    "strikes": [100.0, 105.0, 110.0, 115.0, 120.0]
                },
                {
                    "date": "2024-02-02",
                    "strikes": [100.0, 105.0, 110.0, 115.0, 120.0]
                }
            ]
        }
    
    monkeypatch.setattr(tradier, 'get_options_expirations_tradier', mock_get_expirations)
    return mock_get_expirations


@pytest.fixture
def mock_tradier_chain(monkeypatch):
    """Mock Tradier options chain API response."""
    from app.vendors import tradier
    
    async def mock_get_chain(symbol: str, expiry: str):
        return {
            "symbol": symbol.upper(),
            "expiry": expiry,
            "contracts": [
                {
                    "symbol": symbol.upper(),
                    "expiry": expiry,
                    "strike": 100.0,
                    "type": "call",
                    "bid": 5.50,
                    "ask": 5.60,
                    "last": 5.55,
                    "volume": 1000,
                    "open_interest": 5000,
                    "delta": 0.5,
                    "gamma": 0.02,
                    "theta": -0.05,
                    "vega": 0.15,
                    "iv": 0.25
                },
                {
                    "symbol": symbol.upper(),
                    "expiry": expiry,
                    "strike": 100.0,
                    "type": "put",
                    "bid": 4.50,
                    "ask": 4.60,
                    "last": 4.55,
                    "volume": 800,
                    "open_interest": 4000,
                    "delta": -0.5,
                    "gamma": 0.02,
                    "theta": -0.05,
                    "vega": 0.15,
                    "iv": 0.25
                }
            ]
        }
    
    monkeypatch.setattr(tradier, 'get_option_chain_tradier', mock_get_chain)
    return mock_get_chain


@pytest.fixture
def mock_occ_refresh(monkeypatch):
    """Mock OCC symbols refresh function."""
    from app.services import occ_symbols
    
    async def mock_refresh(raise_on_error: bool = False):
        # Simulate successful refresh
        pass
    
    monkeypatch.setattr(occ_symbols, 'refresh_symbols', mock_refresh)
    return mock_refresh

