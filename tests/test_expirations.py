# tests/test_expirations.py
"""
Tests for options expirations endpoint.
"""
import pytest


def test_expirations_endpoint_missing_symbol(client):
    """Test expirations endpoint without symbol parameter."""
    response = client.get("/v1/markets/options/expirations")
    assert response.status_code == 422  # Validation error


def test_expirations_endpoint_with_symbol(client, mock_tradier_expirations):
    """Test expirations endpoint with valid symbol."""
    response = client.get("/v1/markets/options/expirations?symbol=AAPL")
    assert response.status_code == 200
    
    data = response.json()
    assert "symbol" in data
    assert "expirations" in data
    assert "expiration_data" in data
    
    assert data["symbol"] == "AAPL"
    assert isinstance(data["expirations"], list)
    assert isinstance(data["expiration_data"], list)
    assert len(data["expirations"]) > 0
    assert len(data["expiration_data"]) > 0


def test_expirations_endpoint_structure(client, mock_tradier_expirations):
    """Test expirations endpoint returns correct data structure."""
    response = client.get("/v1/markets/options/expirations?symbol=NFLX")
    assert response.status_code == 200
    
    data = response.json()
    
    # Check expirations list
    assert all(isinstance(date, str) for date in data["expirations"])
    
    # Check expiration_data structure
    for exp_data in data["expiration_data"]:
        assert "date" in exp_data
        assert "strikes" in exp_data
        assert isinstance(exp_data["date"], str)
        assert isinstance(exp_data["strikes"], list)
        assert all(isinstance(strike, (int, float)) for strike in exp_data["strikes"])


def test_expirations_endpoint_symbol_uppercase(client, mock_tradier_expirations):
    """Test that symbol is converted to uppercase."""
    response = client.get("/v1/markets/options/expirations?symbol=aapl")
    assert response.status_code == 200
    
    data = response.json()
    assert data["symbol"] == "AAPL"


def test_expirations_endpoint_includes_strikes(client, mock_tradier_expirations):
    """Test that expiration_data includes strikes."""
    response = client.get("/v1/markets/options/expirations?symbol=MSFT")
    assert response.status_code == 200
    
    data = response.json()
    assert len(data["expiration_data"]) > 0
    
    # Check that at least one expiration has strikes
    has_strikes = any(len(exp["strikes"]) > 0 for exp in data["expiration_data"])
    assert has_strikes

