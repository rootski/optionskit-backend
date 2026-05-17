# tests/test_vendors_tradier.py
"""
Unit tests for the Tradier vendor module.
All HTTP calls are intercepted with httpx mock transport — no real API calls.
"""
import pytest
import httpx
from unittest.mock import patch, AsyncMock

from app.vendors import tradier as tradier_module
from app.vendors.tradier import (
    get_option_chain_tradier,
    get_options_expirations_tradier,
    get_quotes_tradier,
    _f,
    _i,
    _f_or_none,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_response(json_body: dict, status_code: int = 200) -> httpx.Response:
    return httpx.Response(status_code, json=json_body)


def _make_transport(json_body: dict, status_code: int = 200):
    """Return an httpx.MockTransport that always returns the given response."""
    response = _mock_response(json_body, status_code)

    class _Transport(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request):
            return response

    return _Transport()


# ---------------------------------------------------------------------------
# Helper function unit tests
# ---------------------------------------------------------------------------

def test_f_happy():
    assert _f(1.5) == 1.5
    assert _f("2.0") == 2.0
    assert _f(None) == 0.0
    assert _f(None, default=99.0) == 99.0

def test_f_bad_value():
    assert _f("not-a-number") == 0.0
    assert _f([]) == 0.0

def test_i_happy():
    assert _i(5) == 5
    assert _i("10") == 10
    assert _i(None) == 0

def test_i_bad_value():
    assert _i("bad") == 0

def test_f_or_none_happy():
    assert _f_or_none(0.5) == 0.5
    assert _f_or_none("1.2") == 1.2

def test_f_or_none_returns_none():
    assert _f_or_none(None) is None
    assert _f_or_none("bad") is None


# ---------------------------------------------------------------------------
# get_quotes_tradier
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_quotes_empty_list():
    result = await get_quotes_tradier([])
    assert result == []


@pytest.mark.asyncio
async def test_get_quotes_no_token():
    with patch.object(tradier_module, "TRADIER_API_TOKEN", ""):
        with pytest.raises(RuntimeError, match="TRADIER_API_TOKEN not set"):
            await get_quotes_tradier(["AAPL"])


@pytest.mark.asyncio
async def test_get_quotes_single_symbol():
    payload = {
        "quotes": {
            "quote": {
                "symbol": "AAPL",
                "description": "Apple Inc",
                "last": 175.0,
                "bid": 174.9,
                "ask": 175.1,
                "volume": 50000000,
                "exchange": "Q",
                "trade_time": "2026-05-17T16:00:00",
                "change": 1.5,
                "change_percent": 0.86,
            }
        }
    }
    with patch("httpx.AsyncClient", return_value=httpx.AsyncClient(transport=_make_transport(payload))):
        result = await get_quotes_tradier(["AAPL"])

    assert len(result) == 1
    assert result[0]["symbol"] == "AAPL"
    assert result[0]["last"] == 175.0
    assert result[0]["bid"] == 174.9
    assert result[0]["ask"] == 175.1
    assert result[0]["volume"] == 50000000
    assert result[0]["description"] == "Apple Inc"


@pytest.mark.asyncio
async def test_get_quotes_multiple_symbols():
    payload = {
        "quotes": {
            "quote": [
                {"symbol": "AAPL", "last": 175.0, "bid": 174.9, "ask": 175.1,
                 "volume": 1000, "description": "Apple", "exchange": "Q",
                 "trade_time": "", "change": 0.0, "change_percent": 0.0},
                {"symbol": "MSFT", "last": 420.0, "bid": 419.5, "ask": 420.5,
                 "volume": 2000, "description": "Microsoft", "exchange": "Q",
                 "trade_time": "", "change": 0.0, "change_percent": 0.0},
            ]
        }
    }
    with patch("httpx.AsyncClient", return_value=httpx.AsyncClient(transport=_make_transport(payload))):
        result = await get_quotes_tradier(["AAPL", "MSFT"])

    assert len(result) == 2
    symbols = {r["symbol"] for r in result}
    assert symbols == {"AAPL", "MSFT"}


@pytest.mark.asyncio
async def test_get_quotes_null_quotes_field():
    """Tradier returns {"quotes": null} — should return empty list."""
    payload = {"quotes": None}
    with patch("httpx.AsyncClient", return_value=httpx.AsyncClient(transport=_make_transport(payload))):
        result = await get_quotes_tradier(["AAPL"])
    assert result == []


@pytest.mark.asyncio
async def test_get_quotes_empty_quotes_dict():
    payload = {"quotes": {}}
    with patch("httpx.AsyncClient", return_value=httpx.AsyncClient(transport=_make_transport(payload))):
        result = await get_quotes_tradier(["AAPL"])
    assert result == []


@pytest.mark.asyncio
async def test_get_quotes_null_quote_field():
    """quotes.quote is null — should return empty list."""
    payload = {"quotes": {"quote": None}}
    with patch("httpx.AsyncClient", return_value=httpx.AsyncClient(transport=_make_transport(payload))):
        result = await get_quotes_tradier(["AAPL"])
    assert result == []


@pytest.mark.asyncio
async def test_get_quotes_missing_fields_default_to_zero():
    """Quotes with missing numeric fields should default to 0."""
    payload = {
        "quotes": {
            "quote": {"symbol": "XYZ", "description": "XYZ Corp"}
        }
    }
    with patch("httpx.AsyncClient", return_value=httpx.AsyncClient(transport=_make_transport(payload))):
        result = await get_quotes_tradier(["XYZ"])

    assert len(result) == 1
    assert result[0]["last"] == 0.0
    assert result[0]["bid"] == 0.0
    assert result[0]["volume"] == 0


@pytest.mark.asyncio
async def test_get_quotes_401_raises():
    with patch("httpx.AsyncClient", return_value=httpx.AsyncClient(transport=_make_transport({}, 401))):
        with pytest.raises(httpx.HTTPStatusError):
            await get_quotes_tradier(["AAPL"])


@pytest.mark.asyncio
async def test_get_quotes_403_raises():
    with patch("httpx.AsyncClient", return_value=httpx.AsyncClient(transport=_make_transport({}, 403))):
        with pytest.raises(httpx.HTTPStatusError):
            await get_quotes_tradier(["AAPL"])


@pytest.mark.asyncio
async def test_get_quotes_500_raises():
    with patch("httpx.AsyncClient", return_value=httpx.AsyncClient(transport=_make_transport({}, 500))):
        with pytest.raises(httpx.HTTPStatusError):
            await get_quotes_tradier(["AAPL"])


@pytest.mark.asyncio
async def test_get_quotes_symbols_uppercased():
    """Symbols in the request should be uppercased."""
    payload = {
        "quotes": {
            "quote": {"symbol": "AAPL", "last": 175.0, "bid": 174.9,
                      "ask": 175.1, "volume": 1000, "description": "",
                      "exchange": "", "trade_time": "", "change": 0.0,
                      "change_percent": 0.0}
        }
    }
    captured = {}

    class _CapturingTransport(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request):
            captured["url"] = str(request.url)
            return httpx.Response(200, json=payload)

    with patch("httpx.AsyncClient", return_value=httpx.AsyncClient(transport=_CapturingTransport())):
        await get_quotes_tradier(["aapl"])

    assert "AAPL" in captured["url"]


# ---------------------------------------------------------------------------
# get_option_chain_tradier
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_chain_no_token():
    with patch.object(tradier_module, "TRADIER_API_TOKEN", ""):
        with pytest.raises(RuntimeError, match="TRADIER_API_TOKEN not set"):
            await get_option_chain_tradier("AAPL", "2026-06-20")


@pytest.mark.asyncio
async def test_get_chain_happy_path():
    payload = {
        "options": {
            "option": [
                {
                    "expiration_date": "2026-06-20",
                    "strike": 200.0,
                    "option_type": "call",
                    "bid": 5.5,
                    "ask": 5.7,
                    "last": 5.6,
                    "volume": 1000,
                    "open_interest": 5000,
                    "greeks": {
                        "delta": 0.55,
                        "gamma": 0.02,
                        "theta": -0.05,
                        "vega": 0.15,
                        "mid_iv": 0.25,
                        "rho": 0.03,
                    }
                }
            ]
        }
    }
    with patch("httpx.AsyncClient", return_value=httpx.AsyncClient(transport=_make_transport(payload))):
        result = await get_option_chain_tradier("AAPL", "2026-06-20")

    assert result["symbol"] == "AAPL"
    assert result["expiry"] == "2026-06-20"
    assert len(result["contracts"]) == 1
    c = result["contracts"][0]
    assert c["strike"] == 200.0
    assert c["type"] == "call"
    assert c["bid"] == 5.5
    assert c["delta"] == 0.55
    assert c["iv"] == 0.25


@pytest.mark.asyncio
async def test_get_chain_rho_present():
    payload = {
        "options": {
            "option": [{
                "expiration_date": "2026-06-20", "strike": 200.0,
                "option_type": "call", "bid": 1.0, "ask": 1.1, "last": 1.05,
                "volume": 100, "open_interest": 500,
                "greeks": {"delta": 0.5, "gamma": 0.01, "theta": -0.02,
                           "vega": 0.1, "mid_iv": 0.2, "rho": 0.04}
            }]
        }
    }
    with patch.object(tradier_module, "ENABLE_RHO_GREEK", True):
        with patch("httpx.AsyncClient", return_value=httpx.AsyncClient(transport=_make_transport(payload))):
            result = await get_option_chain_tradier("AAPL", "2026-06-20")
    assert result["contracts"][0]["rho"] == 0.04


@pytest.mark.asyncio
async def test_get_chain_rho_flag_off():
    payload = {
        "options": {
            "option": [{
                "expiration_date": "2026-06-20", "strike": 200.0,
                "option_type": "call", "bid": 1.0, "ask": 1.1, "last": 1.05,
                "volume": 100, "open_interest": 500,
                "greeks": {"delta": 0.5, "gamma": 0.01, "theta": -0.02,
                           "vega": 0.1, "mid_iv": 0.2, "rho": 0.04}
            }]
        }
    }
    with patch.object(tradier_module, "ENABLE_RHO_GREEK", False):
        with patch("httpx.AsyncClient", return_value=httpx.AsyncClient(transport=_make_transport(payload))):
            result = await get_option_chain_tradier("AAPL", "2026-06-20")
    assert result["contracts"][0]["rho"] is None


@pytest.mark.asyncio
async def test_get_chain_single_option_as_dict():
    """Tradier may return a single option as a dict (not a list)."""
    payload = {
        "options": {
            "option": {
                "expiration_date": "2026-06-20", "strike": 150.0,
                "option_type": "put", "bid": 2.0, "ask": 2.1, "last": 2.05,
                "volume": 200, "open_interest": 1000,
                "greeks": {}
            }
        }
    }
    with patch("httpx.AsyncClient", return_value=httpx.AsyncClient(transport=_make_transport(payload))):
        result = await get_option_chain_tradier("AAPL", "2026-06-20")
    assert len(result["contracts"]) == 1
    assert result["contracts"][0]["type"] == "put"


@pytest.mark.asyncio
async def test_get_chain_filters_wrong_expiry():
    """Contracts with wrong expiry date should be filtered out."""
    payload = {
        "options": {
            "option": [
                {"expiration_date": "2026-06-20", "strike": 200.0,
                 "option_type": "call", "bid": 1.0, "ask": 1.1, "last": 1.05,
                 "volume": 100, "open_interest": 500, "greeks": {}},
                {"expiration_date": "2026-07-18", "strike": 200.0,
                 "option_type": "call", "bid": 2.0, "ask": 2.1, "last": 2.05,
                 "volume": 50, "open_interest": 200, "greeks": {}},
            ]
        }
    }
    with patch("httpx.AsyncClient", return_value=httpx.AsyncClient(transport=_make_transport(payload))):
        result = await get_option_chain_tradier("AAPL", "2026-06-20")
    assert len(result["contracts"]) == 1
    assert result["contracts"][0]["expiry"] == "2026-06-20"


@pytest.mark.asyncio
async def test_get_chain_null_options():
    """options field is null — should return empty contracts."""
    payload = {"options": None}
    with patch("httpx.AsyncClient", return_value=httpx.AsyncClient(transport=_make_transport(payload))):
        result = await get_option_chain_tradier("AAPL", "2026-06-20")
    assert result["contracts"] == []


@pytest.mark.asyncio
async def test_get_chain_missing_options_key():
    payload = {}
    with patch("httpx.AsyncClient", return_value=httpx.AsyncClient(transport=_make_transport(payload))):
        result = await get_option_chain_tradier("AAPL", "2026-06-20")
    assert result["contracts"] == []


@pytest.mark.asyncio
async def test_get_chain_401_raises():
    with patch("httpx.AsyncClient", return_value=httpx.AsyncClient(transport=_make_transport({}, 401))):
        with pytest.raises(httpx.HTTPStatusError):
            await get_option_chain_tradier("AAPL", "2026-06-20")


@pytest.mark.asyncio
async def test_get_chain_null_greeks():
    """greeks field is null — greek values should default to 0."""
    payload = {
        "options": {
            "option": [{
                "expiration_date": "2026-06-20", "strike": 200.0,
                "option_type": "call", "bid": 1.0, "ask": 1.1, "last": 1.05,
                "volume": 100, "open_interest": 500,
                "greeks": None
            }]
        }
    }
    with patch("httpx.AsyncClient", return_value=httpx.AsyncClient(transport=_make_transport(payload))):
        result = await get_option_chain_tradier("AAPL", "2026-06-20")
    c = result["contracts"][0]
    assert c["delta"] == 0.0
    assert c["gamma"] == 0.0
    assert c["iv"] == 0.0


# ---------------------------------------------------------------------------
# get_options_expirations_tradier
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_expirations_no_token():
    with patch.object(tradier_module, "TRADIER_API_TOKEN", ""):
        with pytest.raises(RuntimeError, match="TRADIER_API_TOKEN not set"):
            await get_options_expirations_tradier("AAPL")


@pytest.mark.asyncio
async def test_get_expirations_date_list_with_strikes():
    """Standard response: list of date objects with strikes."""
    payload = {
        "expirations": {
            "date": [
                {"expiration_date": "2026-06-20", "strikes": {"strike": [190.0, 195.0, 200.0]}},
                {"expiration_date": "2026-07-18", "strikes": {"strike": [190.0, 200.0]}},
            ]
        }
    }
    with patch("httpx.AsyncClient", return_value=httpx.AsyncClient(transport=_make_transport(payload))):
        result = await get_options_expirations_tradier("AAPL")

    assert result["symbol"] == "AAPL"
    assert "2026-06-20" in result["expirations"]
    assert "2026-07-18" in result["expirations"]
    assert len(result["expiration_data"]) == 2
    assert result["expiration_data"][0]["strikes"] == [190.0, 195.0, 200.0]


@pytest.mark.asyncio
async def test_get_expirations_simple_date_strings():
    """Older response format: list of plain date strings."""
    payload = {
        "expirations": {
            "date": ["2026-06-20", "2026-07-18"]
        }
    }
    with patch("httpx.AsyncClient", return_value=httpx.AsyncClient(transport=_make_transport(payload))):
        result = await get_options_expirations_tradier("AAPL")

    assert result["expirations"] == ["2026-06-20", "2026-07-18"]
    assert result["expiration_data"][0]["strikes"] == []


@pytest.mark.asyncio
async def test_get_expirations_single_date_string():
    """Single date returned as string (not list)."""
    payload = {
        "expirations": {
            "date": "2026-06-20"
        }
    }
    with patch("httpx.AsyncClient", return_value=httpx.AsyncClient(transport=_make_transport(payload))):
        result = await get_options_expirations_tradier("AAPL")

    assert result["expirations"] == ["2026-06-20"]


@pytest.mark.asyncio
async def test_get_expirations_single_strike_as_scalar():
    """Single strike returned as number (not list)."""
    payload = {
        "expirations": {
            "date": [
                {"expiration_date": "2026-06-20", "strikes": {"strike": 200.0}}
            ]
        }
    }
    with patch("httpx.AsyncClient", return_value=httpx.AsyncClient(transport=_make_transport(payload))):
        result = await get_options_expirations_tradier("AAPL")

    assert result["expiration_data"][0]["strikes"] == [200.0]


@pytest.mark.asyncio
async def test_get_expirations_missing_key():
    """No 'expirations' key — should return empty lists."""
    payload = {}
    with patch("httpx.AsyncClient", return_value=httpx.AsyncClient(transport=_make_transport(payload))):
        result = await get_options_expirations_tradier("AAPL")

    assert result["expirations"] == []
    assert result["expiration_data"] == []


@pytest.mark.asyncio
async def test_get_expirations_symbol_uppercased():
    payload = {"expirations": {"date": []}}
    with patch("httpx.AsyncClient", return_value=httpx.AsyncClient(transport=_make_transport(payload))):
        result = await get_options_expirations_tradier("aapl")
    assert result["symbol"] == "AAPL"


@pytest.mark.asyncio
async def test_get_expirations_401_raises():
    with patch("httpx.AsyncClient", return_value=httpx.AsyncClient(transport=_make_transport({}, 401))):
        with pytest.raises(httpx.HTTPStatusError):
            await get_options_expirations_tradier("AAPL")
