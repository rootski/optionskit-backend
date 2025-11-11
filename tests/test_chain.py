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

