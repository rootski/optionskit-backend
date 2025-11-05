import httpx

from ..config import MASSIVE_BASE_URL, MASSIVE_API_KEY


# Helper to safely parse numbers
def _f(x, default=0.0):
    try:
        return float(x) if x is not None else default
    except Exception:
        return default

def _i(x, default=0):
    try:
        return int(x) if x is not None else default
    except Exception:
        return default


async def get_option_chain_snapshot(symbol: str, expiry: str):
    """
    Fetch a per-underlying options snapshot and filter to a single expiry.

    symbol: "AAPL", "NFLX", etc.
    expiry: "YYYY-MM-DD" (e.g., "2025-11-07")
    """

    # Common snapshot endpoint for Polygon (Massive)
    # Example shape: GET /v3/snapshot/options/{underlying}?expiration_date=YYYY-MM-DD&limit=1000&apiKey=...
    url = f"{MASSIVE_BASE_URL}/v3/snapshot/options/{symbol.upper()}"
    params = {
        "expiration_date": expiry,  # if your plan uses a different param name, adjust here
        "limit": 1000,
        "apiKey": MASSIVE_API_KEY
    }

    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.get(url, params=params)
        r.raise_for_status()
        data = r.json()

    # Polygon-style responses often place data under "results" (list)
    results = data.get("results", []) or data.get("options", []) or []

    contracts = []
    for item in results:
        # Try to read common fields from snapshot payloads
        # (field names vary slightly across endpoints; we use multiple lookups)
        o = item.get("details", {}) or item.get("contract", {}) or {}
        q = item.get("last_quote", {}) or item.get("quote", {}) or {}
        g = item.get("greeks", {}) or {}

        # Fallbacks: some snapshots put prices at top-level
        bid = _f(q.get("bid") or item.get("bid"))
        ask = _f(q.get("ask") or item.get("ask"))
        last = _f(item.get("last") or item.get("close") or q.get("last"))

        contracts.append({
            "symbol": symbol.upper(),
            "expiry": o.get("expiration_date") or item.get("expiration_date") or expiry,
            "strike": _f(o.get("strike_price") or item.get("strike")),
            "type": (o.get("contract_type") or item.get("contract_type") or "").lower(),  # "call"/"put"
            "bid": bid,
            "ask": ask,
            "last": last,
            "volume": _i(item.get("day", {}).get("volume") or item.get("volume")),
            "open_interest": _i(item.get("open_interest")),
            "delta": _f(g.get("delta")),
            "gamma": _f(g.get("gamma")),
            "theta": _f(g.get("theta")),
            "vega": _f(g.get("vega")),
            "iv": _f(g.get("iv") or item.get("implied_volatility")),
        })

    # Keep only exact expiry matches (defensive)
    contracts = [c for c in contracts if c["expiry"] == expiry]

    return {
        "symbol": symbol.upper(),
        "expiry": expiry,
        "contracts": contracts
    }
