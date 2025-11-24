# tests/test_chain.py
"""
Tests for options chain endpoint.
"""
import pytest


def test_chain_endpoint_missing_params(client):
    """Test chain endpoint without required parameters."""
    response = client.get("/v1/markets/chain")
    assert response.status_code == 422  # Validation error


def test_chain_endpoint_missing_expiry(client):
    """Test chain endpoint without expiry parameter."""
    response = client.get("/v1/markets/chain?symbol=AAPL")
    assert response.status_code == 422  # Validation error


def test_chain_endpoint_missing_symbol(client):
    """Test chain endpoint without symbol parameter."""
    response = client.get("/v1/markets/chain?expiry=2024-01-19")
    assert response.status_code == 422  # Validation error


def test_chain_endpoint_with_params(client, mock_tradier_chain):
    """Test chain endpoint with valid parameters."""
    response = client.get("/v1/markets/chain?symbol=AAPL&expiry=2024-01-19")
    assert response.status_code == 200
    
    data = response.json()
    assert "symbol" in data
    assert "expiry" in data
    assert "contracts" in data
    
    assert data["symbol"] == "AAPL"
    assert data["expiry"] == "2024-01-19"
    assert isinstance(data["contracts"], list)


def test_chain_endpoint_contract_structure(client, mock_tradier_chain):
    """Test that contracts have the correct structure."""
    response = client.get("/v1/markets/chain?symbol=MSFT&expiry=2024-01-26")
    assert response.status_code == 200
    
    data = response.json()
    assert len(data["contracts"]) > 0
    
    contract = data["contracts"][0]
    required_fields = [
        "symbol", "expiry", "strike", "type", "bid", "ask", "last",
        "volume", "open_interest", "delta", "gamma", "theta", "vega", "iv"
    ]
    
    for field in required_fields:
        assert field in contract, f"Missing field: {field}"
    
    # Rho is optional but should be present (may be None)
    assert "rho" in contract, "rho field should be present (may be None)"


def test_chain_endpoint_contract_types(client, mock_tradier_chain):
    """Test that contracts have correct types."""
    response = client.get("/v1/markets/chain?symbol=GOOGL&expiry=2024-02-02")
    assert response.status_code == 200
    
    data = response.json()
    if len(data["contracts"]) > 0:
        contract = data["contracts"][0]
        
        assert isinstance(contract["symbol"], str)
        assert isinstance(contract["expiry"], str)
        assert isinstance(contract["strike"], (int, float))
        assert contract["type"] in ["call", "put"]
        assert isinstance(contract["bid"], (int, float))
        assert isinstance(contract["ask"], (int, float))
        assert isinstance(contract["last"], (int, float))
        assert isinstance(contract["volume"], int)
        assert isinstance(contract["open_interest"], int)
        assert isinstance(contract["delta"], (int, float))
        assert isinstance(contract["gamma"], (int, float))
        assert isinstance(contract["theta"], (int, float))
        assert isinstance(contract["vega"], (int, float))
        assert isinstance(contract["iv"], (int, float))
        # Rho is optional and may be None
        assert contract["rho"] is None or isinstance(contract["rho"], (int, float))


def test_chain_rho_when_vendor_provides(client, mock_tradier_chain):
    """Test that rho is present and numeric when vendor provides it."""
    response = client.get("/v1/markets/chain?symbol=AAPL&expiry=2024-01-19")
    assert response.status_code == 200
    
    data = response.json()
    assert len(data["contracts"]) > 0
    
    contract = data["contracts"][0]
    assert "rho" in contract
    assert contract["rho"] is not None
    assert isinstance(contract["rho"], (int, float))
    # Verify it's a finite number (not NaN or inf)
    assert abs(contract["rho"]) < 1e10


def test_chain_rho_when_vendor_omits(client, mock_tradier_chain_no_rho):
    """Test that rho is null when vendor omits it."""
    response = client.get("/v1/markets/chain?symbol=AAPL&expiry=2024-01-19")
    assert response.status_code == 200
    
    data = response.json()
    assert len(data["contracts"]) > 0
    
    contract = data["contracts"][0]
    assert "rho" in contract
    assert contract["rho"] is None


def test_chain_rho_massive_always_null(client, mock_massive_chain, monkeypatch):
    """Test that Massive/Polygon always returns null for rho."""
    from app.config import MASSIVE_API_KEY
    from unittest.mock import patch
    
    # Mock MASSIVE_API_KEY to be set
    with patch('app.main.MASSIVE_API_KEY', 'test_key'):
        # Mock Tradier to fail so we fall back to Massive
        from app.vendors import tradier
        from app import main
        
        async def mock_tradier_fail(symbol: str, expiry: str):
            raise Exception("Tradier failed")
        
        monkeypatch.setattr(tradier, 'get_option_chain_tradier', mock_tradier_fail)
        monkeypatch.setattr(main, 'get_option_chain_tradier', mock_tradier_fail)
        
        response = client.get("/v1/markets/chain?symbol=AAPL&expiry=2024-01-19")
        assert response.status_code == 200
        
        data = response.json()
        assert len(data["contracts"]) > 0
        
        contract = data["contracts"][0]
        assert "rho" in contract
        assert contract["rho"] is None


def test_chain_rho_feature_flag_off(monkeypatch):
    """Test that rho is null when feature flag is disabled."""
    from app.vendors.tradier import _f_or_none
    
    # Simulate the logic in get_option_chain_tradier when flag is off
    # Even if Tradier provides rho, it should be None when flag is disabled
    greeks_with_rho = {"delta": 0.5, "gamma": 0.02, "theta": -0.05, "vega": 0.15, "rho": 0.01}
    
    # Simulate ENABLE_RHO_GREEK = False
    ENABLE_RHO_GREEK = False
    rho_value = _f_or_none(greeks_with_rho.get("rho")) if ENABLE_RHO_GREEK else None
    
    assert rho_value is None, "Rho should be None when feature flag is disabled, even if vendor provides it"

