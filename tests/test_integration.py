# tests/test_integration.py
"""
Integration tests for critical paths.
"""
import pytest


def test_version_includes_occ_timestamp(client, mock_occ_symbols):
    """Integration test: Version API includes OCC timestamp."""
    response = client.get("/version")
    assert response.status_code == 200
    
    data = response.json()
    # OCC timestamp should be present if symbols are loaded
    assert "occ_symbols_last_update" in data


def test_symbols_endpoint_after_refresh(client, mock_occ_refresh, mock_occ_symbols):
    """Integration test: Symbols endpoint works after refresh."""
    # First refresh
    refresh_response = client.post("/v1/markets/options/symbols/refresh")
    
    # Then get symbols
    symbols_response = client.get("/v1/markets/options/symbols")
    assert symbols_response.status_code == 200
    
    data = symbols_response.json()
    assert data["count"] > 0
    assert len(data["symbols"]) > 0


def test_expirations_for_symbol_in_list(client, mock_tradier_expirations, mock_occ_symbols):
    """Integration test: Can get expirations for a symbol that's in the symbols list."""
    # Get symbols list
    symbols_response = client.get("/v1/markets/options/symbols")
    assert symbols_response.status_code == 200
    symbols = symbols_response.json()["symbols"]
    
    if len(symbols) > 0:
        # Try to get expirations for first symbol
        test_symbol = symbols[0]
        expirations_response = client.get(f"/v1/markets/options/expirations?symbol={test_symbol}")
        assert expirations_response.status_code == 200
        
        data = expirations_response.json()
        assert data["symbol"] == test_symbol.upper()

