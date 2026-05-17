# tests/test_vendors_massive.py
"""
Unit tests for the Massive (Polygon) vendor module.
All HTTP calls are intercepted with httpx mock transport — no real API calls.
"""
import pytest
import httpx
from unittest.mock import patch

from app.vendors.massive import get_option_chain_snapshot


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_transport(json_body: dict, status_code: int = 200):
    response = httpx.Response(status_code, json=json_body)

    class _Transport(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request):
            return response

    return _Transport()


# ---------------------------------------------------------------------------
# get_option_chain_snapshot
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_chain_happy_path():
    payload = {
        "results": [
            {
                "details": {
                    "expiration_date": "2026-06-20",
                    "strike_price": 200.0,
                    "contract_type": "call",
                },
                "last_quote": {"bid": 5.5, "ask": 5.7},
                "last": 5.6,
                "day": {"volume": 1000},
                "open_interest": 5000,
                "greeks": {
                    "delta": 0.55,
                    "gamma": 0.02,
                    "theta": -0.05,
                    "vega": 0.15,
                    "iv": 0.25,
                },
            }
        ]
    }
    with patch("httpx.AsyncClient", return_value=httpx.AsyncClient(transport=_make_transport(payload))):
        result = await get_option_chain_snapshot("AAPL", "2026-06-20")

    assert result["symbol"] == "AAPL"
    assert result["expiry"] == "2026-06-20"
    assert len(result["contracts"]) == 1
    c = result["contracts"][0]
    assert c["strike"] == 200.0
    assert c["type"] == "call"
    assert c["bid"] == 5.5
    assert c["ask"] == 5.7
    assert c["last"] == 5.6
    assert c["volume"] == 1000
    assert c["open_interest"] == 5000
    assert c["delta"] == 0.55
    assert c["iv"] == 0.25


@pytest.mark.asyncio
async def test_get_chain_rho_always_none():
    """Massive/Polygon never provides rho — should always be None."""
    payload = {
        "results": [{
            "details": {"expiration_date": "2026-06-20", "strike_price": 200.0,
                        "contract_type": "call"},
            "last_quote": {"bid": 1.0, "ask": 1.1},
            "last": 1.05,
            "day": {"volume": 100},
            "open_interest": 500,
            "greeks": {"delta": 0.5, "gamma": 0.01, "theta": -0.02,
                       "vega": 0.1, "iv": 0.2},
        }]
    }
    with patch("httpx.AsyncClient", return_value=httpx.AsyncClient(transport=_make_transport(payload))):
        result = await get_option_chain_snapshot("AAPL", "2026-06-20")
    assert result["contracts"][0]["rho"] is None


@pytest.mark.asyncio
async def test_get_chain_empty_results():
    payload = {"results": []}
    with patch("httpx.AsyncClient", return_value=httpx.AsyncClient(transport=_make_transport(payload))):
        result = await get_option_chain_snapshot("AAPL", "2026-06-20")
    assert result["contracts"] == []


@pytest.mark.asyncio
async def test_get_chain_missing_results_key():
    """No 'results' key — should return empty contracts."""
    payload = {}
    with patch("httpx.AsyncClient", return_value=httpx.AsyncClient(transport=_make_transport(payload))):
        result = await get_option_chain_snapshot("AAPL", "2026-06-20")
    assert result["contracts"] == []


@pytest.mark.asyncio
async def test_get_chain_options_key_fallback():
    """Some Polygon responses use 'options' instead of 'results'."""
    payload = {
        "options": [{
            "details": {"expiration_date": "2026-06-20", "strike_price": 150.0,
                        "contract_type": "put"},
            "last_quote": {"bid": 3.0, "ask": 3.2},
            "last": 3.1,
            "day": {"volume": 500},
            "open_interest": 2000,
            "greeks": {},
        }]
    }
    with patch("httpx.AsyncClient", return_value=httpx.AsyncClient(transport=_make_transport(payload))):
        result = await get_option_chain_snapshot("AAPL", "2026-06-20")
    assert len(result["contracts"]) == 1
    assert result["contracts"][0]["type"] == "put"


@pytest.mark.asyncio
async def test_get_chain_filters_wrong_expiry():
    """Contracts with a different expiry date should be filtered out."""
    payload = {
        "results": [
            {"details": {"expiration_date": "2026-06-20", "strike_price": 200.0,
                         "contract_type": "call"},
             "last_quote": {"bid": 1.0, "ask": 1.1}, "last": 1.05,
             "day": {"volume": 100}, "open_interest": 500, "greeks": {}},
            {"details": {"expiration_date": "2026-07-18", "strike_price": 200.0,
                         "contract_type": "call"},
             "last_quote": {"bid": 2.0, "ask": 2.1}, "last": 2.05,
             "day": {"volume": 50}, "open_interest": 200, "greeks": {}},
        ]
    }
    with patch("httpx.AsyncClient", return_value=httpx.AsyncClient(transport=_make_transport(payload))):
        result = await get_option_chain_snapshot("AAPL", "2026-06-20")
    assert len(result["contracts"]) == 1
    assert result["contracts"][0]["expiry"] == "2026-06-20"


@pytest.mark.asyncio
async def test_get_chain_symbol_uppercased():
    payload = {"results": []}
    with patch("httpx.AsyncClient", return_value=httpx.AsyncClient(transport=_make_transport(payload))):
        result = await get_option_chain_snapshot("aapl", "2026-06-20")
    assert result["symbol"] == "AAPL"


@pytest.mark.asyncio
async def test_get_chain_top_level_bid_ask_fallback():
    """Bid/ask at top level (not in last_quote) should be picked up."""
    payload = {
        "results": [{
            "details": {"expiration_date": "2026-06-20", "strike_price": 200.0,
                        "contract_type": "call"},
            "bid": 4.0,
            "ask": 4.2,
            "last": 4.1,
            "day": {"volume": 300},
            "open_interest": 1500,
            "greeks": {},
        }]
    }
    with patch("httpx.AsyncClient", return_value=httpx.AsyncClient(transport=_make_transport(payload))):
        result = await get_option_chain_snapshot("AAPL", "2026-06-20")
    c = result["contracts"][0]
    assert c["bid"] == 4.0
    assert c["ask"] == 4.2


@pytest.mark.asyncio
async def test_get_chain_missing_greeks_default_zero():
    """Missing greeks should default to 0.0."""
    payload = {
        "results": [{
            "details": {"expiration_date": "2026-06-20", "strike_price": 200.0,
                        "contract_type": "call"},
            "last_quote": {"bid": 1.0, "ask": 1.1},
            "last": 1.05,
            "day": {"volume": 100},
            "open_interest": 500,
        }]
    }
    with patch("httpx.AsyncClient", return_value=httpx.AsyncClient(transport=_make_transport(payload))):
        result = await get_option_chain_snapshot("AAPL", "2026-06-20")
    c = result["contracts"][0]
    assert c["delta"] == 0.0
    assert c["iv"] == 0.0


@pytest.mark.asyncio
async def test_get_chain_403_raises():
    with patch("httpx.AsyncClient", return_value=httpx.AsyncClient(transport=_make_transport({}, 403))):
        with pytest.raises(httpx.HTTPStatusError):
            await get_option_chain_snapshot("AAPL", "2026-06-20")


@pytest.mark.asyncio
async def test_get_chain_401_raises():
    with patch("httpx.AsyncClient", return_value=httpx.AsyncClient(transport=_make_transport({}, 401))):
        with pytest.raises(httpx.HTTPStatusError):
            await get_option_chain_snapshot("AAPL", "2026-06-20")


@pytest.mark.asyncio
async def test_get_chain_500_raises():
    with patch("httpx.AsyncClient", return_value=httpx.AsyncClient(transport=_make_transport({}, 500))):
        with pytest.raises(httpx.HTTPStatusError):
            await get_option_chain_snapshot("AAPL", "2026-06-20")


@pytest.mark.asyncio
async def test_get_chain_contract_type_lowercased():
    """Contract type should always be lowercase."""
    payload = {
        "results": [{
            "details": {"expiration_date": "2026-06-20", "strike_price": 200.0,
                        "contract_type": "CALL"},
            "last_quote": {"bid": 1.0, "ask": 1.1},
            "last": 1.05, "day": {"volume": 100}, "open_interest": 500, "greeks": {},
        }]
    }
    with patch("httpx.AsyncClient", return_value=httpx.AsyncClient(transport=_make_transport(payload))):
        result = await get_option_chain_snapshot("AAPL", "2026-06-20")
    assert result["contracts"][0]["type"] == "call"
