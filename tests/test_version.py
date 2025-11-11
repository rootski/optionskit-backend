# tests/test_version.py
"""
Tests for version API endpoint.
"""
import pytest
from datetime import datetime


def test_version_endpoint(client, mock_occ_symbols):
    """Test the version endpoint returns all required fields."""
    response = client.get("/version")
    assert response.status_code == 200
    
    data = response.json()
    assert "version" in data
    assert "git_sha" in data
    assert "git_tag" in data
    assert "occ_symbols_last_update" in data
    
    # Check types
    assert isinstance(data["version"], str)
    assert isinstance(data["git_sha"], str)
    # git_tag can be None or string
    assert data["git_tag"] is None or isinstance(data["git_tag"], str)
    # occ_symbols_last_update can be None or ISO string
    assert data["occ_symbols_last_update"] is None or isinstance(data["occ_symbols_last_update"], str)


def test_version_endpoint_occ_timestamp_format(client, mock_occ_symbols):
    """Test that OCC timestamp is in ISO format when present."""
    response = client.get("/version")
    assert response.status_code == 200
    
    data = response.json()
    if data["occ_symbols_last_update"]:
        # Should be valid ISO format
        try:
            datetime.fromisoformat(data["occ_symbols_last_update"].replace('Z', '+00:00'))
        except ValueError:
            pytest.fail("occ_symbols_last_update is not in valid ISO format")

