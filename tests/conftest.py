# tests/conftest.py
"""
Shared fixtures for all tests.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient
from datetime import datetime

# Import and patch BEFORE app import to prevent real API calls
import sys
from unittest.mock import patch

# Create a patcher that will be active during app import
_patchers = []

def pytest_configure(config):
    """Configure pytest - set up mocks before any imports."""
    # Patch the functions before app is imported
    patcher1 = patch('app.services.occ_symbols.refresh_symbols', new_callable=AsyncMock)
    patcher2 = patch('app.services.occ_symbols.get_symbols', return_value=set())
    patcher3 = patch('app.services.occ_symbols.get_symbol_count', return_value=0)
    patcher4 = patch('app.services.occ_symbols.get_last_update', return_value=None)
    patcher5 = patch('app.main.scheduler.start')
    patcher6 = patch('app.main.scheduler.shutdown')
    patcher7 = patch('app.main.scheduler.add_job')
    patcher8 = patch('app.services.snapshot_quotes.start_background_task')  # Prevent auto-start in tests
    
    _patchers.extend([patcher1, patcher2, patcher3, patcher4, patcher5, patcher6, patcher7, patcher8])
    
    # Start all patchers
    for p in _patchers:
        p.start()

def pytest_unconfigure(config):
    """Clean up patches after tests."""
    for p in _patchers:
        p.stop()

# Now import app with patches active
from app.main import app
from app.services import occ_symbols
from app.main import scheduler


@pytest.fixture(autouse=True)
def reset_mocks():
    """Reset mocks before each test."""
    occ_symbols.get_symbols.return_value = set()
    occ_symbols.get_symbol_count.return_value = 0
    occ_symbols.get_last_update.return_value = None
    yield


@pytest.fixture
def client():
    """Create a test client for the API."""
    return TestClient(app)


@pytest.fixture
def mock_occ_symbols(monkeypatch):
    """Mock OCC symbols service to return test symbols."""
    from app import main
    
    test_symbols = {"AAPL", "MSFT", "GOOGL", "NFLX", "TSLA"}
    test_last_update = datetime(2024, 1, 15, 2, 0, 0)
    
    def mock_get_symbols():
        return test_symbols.copy()
    
    def mock_get_symbol_count():
        return len(test_symbols)
    
    def mock_get_last_update():
        return test_last_update
    
    # Patch both the module functions and where they're imported in main
    monkeypatch.setattr(occ_symbols, 'get_symbols', mock_get_symbols)
    monkeypatch.setattr(occ_symbols, 'get_symbol_count', mock_get_symbol_count)
    monkeypatch.setattr(occ_symbols, 'get_last_update', mock_get_last_update)
    
    # Also patch in main where they're imported
    monkeypatch.setattr(main, 'get_symbols', mock_get_symbols)
    monkeypatch.setattr(main, 'get_occ_last_update', mock_get_last_update)
    
    return test_symbols


@pytest.fixture
def mock_tradier_expirations(monkeypatch):
    """Mock Tradier expirations API response."""
    from app.vendors import tradier
    from app import main
    
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
    
    # Patch both the module function and where it's imported in main
    monkeypatch.setattr(tradier, 'get_options_expirations_tradier', mock_get_expirations)
    monkeypatch.setattr(main, 'get_options_expirations_tradier', mock_get_expirations)
    return mock_get_expirations


@pytest.fixture
def mock_tradier_chain(monkeypatch):
    """Mock Tradier options chain API response."""
    from app.vendors import tradier
    from app import main
    
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
                    "iv": 0.25,
                    "rho": 0.01
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
                    "iv": 0.25,
                    "rho": -0.01
                }
            ]
        }
    
    # Patch both the module function and where it's imported in main
    monkeypatch.setattr(tradier, 'get_option_chain_tradier', mock_get_chain)
    monkeypatch.setattr(main, 'get_option_chain_tradier', mock_get_chain)
    return mock_get_chain


@pytest.fixture
def mock_tradier_chain_no_rho(monkeypatch):
    """Mock Tradier options chain API response without rho in greeks."""
    from app.vendors import tradier
    from app import main
    
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
                    "iv": 0.25,
                    "rho": None
                }
            ]
        }
    
    # Patch both the module function and where it's imported in main
    monkeypatch.setattr(tradier, 'get_option_chain_tradier', mock_get_chain)
    monkeypatch.setattr(main, 'get_option_chain_tradier', mock_get_chain)
    return mock_get_chain


@pytest.fixture
def mock_massive_chain(monkeypatch):
    """Mock Massive/Polygon options chain API response."""
    from app.vendors import massive
    from app import main
    
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
                    "iv": 0.25,
                    "rho": None
                }
            ]
        }
    
    # Patch both the module function and where it's imported in main
    monkeypatch.setattr(massive, 'get_option_chain_snapshot', mock_get_chain)
    monkeypatch.setattr(main, 'get_option_chain_snapshot', mock_get_chain)
    return mock_get_chain


@pytest.fixture
def mock_occ_refresh(monkeypatch):
    """Mock OCC symbols refresh function."""
    async def mock_refresh(raise_on_error: bool = False):
        # Simulate successful refresh
        pass
    
    monkeypatch.setattr(occ_symbols, 'refresh_symbols', mock_refresh)
    return mock_refresh
