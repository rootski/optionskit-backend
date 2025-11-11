# tests/test_health.py
"""
Tests for health check endpoints.
"""
import pytest


def test_healthz(client):
    """Test the basic health check endpoint."""
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_secrets_health(client):
    """Test the secrets health check endpoint."""
    response = client.get("/healthz/secrets")
    assert response.status_code == 200
    data = response.json()
    assert "tradier_token_set" in data
    assert isinstance(data["tradier_token_set"], bool)

