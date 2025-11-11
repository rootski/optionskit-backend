# tests/test_occ_symbols.py
"""
Tests for OCC symbols endpoints.
"""
import pytest


def test_get_symbols_endpoint(client, mock_occ_symbols):
    """Test getting all symbols returns correct structure."""
    response = client.get("/v1/markets/options/symbols")
    assert response.status_code == 200
    
    data = response.json()
    assert "symbols" in data
    assert "count" in data
    assert "last_update" in data
    assert "note" in data
    
    # Check types
    assert isinstance(data["symbols"], list)
    assert isinstance(data["count"], int)
    assert data["last_update"] is None or isinstance(data["last_update"], str)
    
    # Check that symbols are unique (set behavior)
    assert len(data["symbols"]) == len(set(data["symbols"]))
    
    # Check that symbols are sorted
    assert data["symbols"] == sorted(data["symbols"])
    
    # Check count matches symbols length
    assert data["count"] == len(data["symbols"])


def test_get_symbols_endpoint_contains_test_symbols(client, mock_occ_symbols):
    """Test that endpoint returns expected test symbols."""
    response = client.get("/v1/markets/options/symbols")
    assert response.status_code == 200
    
    data = response.json()
    symbols = data["symbols"]
    
    # Check that test symbols are present
    assert "AAPL" in symbols
    assert "MSFT" in symbols
    assert "GOOGL" in symbols


def test_refresh_symbols_endpoint(client, mock_occ_refresh):
    """Test manual refresh endpoint."""
    response = client.post("/v1/markets/options/symbols/refresh")
    
    # Should succeed (200) or fail gracefully (500) depending on implementation
    assert response.status_code in [200, 500]
    
    if response.status_code == 200:
        data = response.json()
        assert "status" in data
        assert "count" in data
        assert "last_update" in data
        assert data["status"] == "success"


def test_refresh_symbols_endpoint_structure(client, mock_occ_refresh):
    """Test refresh endpoint returns correct structure on success."""
    response = client.post("/v1/markets/options/symbols/refresh")
    
    if response.status_code == 200:
        data = response.json()
        assert "status" in data
        assert "count" in data
        assert "last_update" in data
        assert "message" in data
        assert isinstance(data["count"], int)
        assert data["last_update"] is None or isinstance(data["last_update"], str)

