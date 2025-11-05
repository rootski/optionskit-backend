# app/vendors/tradier.py
import httpx
from ..config import TRADIER_BASE_URL, TRADIER_API_TOKEN, TRADIER_RATE_LIMIT
from .rate_limiter import RateLimiter

# Global rate limiter instance (shared across all requests)
_rate_limiter = RateLimiter(max_requests=TRADIER_RATE_LIMIT, window_seconds=60)

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

async def get_option_chain_tradier(symbol: str, expiry: str):
    """
    Fetch delayed option chains from Tradier (production or sandbox).
    Docs: GET /markets/options/chains?symbol=...&expiration=...&greeks=true
    
    Rate limiting: Automatically enforces Tradier's rate limits
    - Production: 120 requests per minute
    - Sandbox: 60 requests per minute
    See: https://docs.tradier.com/docs/rate-limiting
    """
    if not TRADIER_API_TOKEN:
        raise RuntimeError("TRADIER_API_TOKEN not set")

    # Wait if necessary to respect rate limits
    await _rate_limiter.acquire()

    headers = {
        "Authorization": f"Bearer {TRADIER_API_TOKEN}",
        "Accept": "application/json",
    }
    params = {"symbol": symbol.upper(), "expiration": expiry, "greeks": "true"}

    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.get(f"{TRADIER_BASE_URL}/markets/options/chains",
                             headers=headers, params=params)
        
        # Update rate limiter state from response headers
        _rate_limiter.update_from_headers(r.headers)
        
        r.raise_for_status()
        data = r.json()

    raw = data.get("options", {}).get("option", []) or []
    if isinstance(raw, dict):
        raw = [raw]

    contracts = []
    for opt in raw:
        g = opt.get("greeks", {}) or {}
        contracts.append({
            "symbol": symbol.upper(),
            "expiry": opt.get("expiration_date") or opt.get("expiration") or expiry,
            "strike": _f(opt.get("strike")),
            "type": (opt.get("option_type") or "").lower(),  # "call"/"put"
            "bid": _f(opt.get("bid")),
            "ask": _f(opt.get("ask")),
            "last": _f(opt.get("last")),
            "volume": _i(opt.get("volume")),
            "open_interest": _i(opt.get("open_interest")),
            # Greeks may or may not be present in sandbox. Use if available.
            "delta": _f(g.get("delta")),
            "gamma": _f(g.get("gamma")),
            "theta": _f(g.get("theta")),
            "vega": _f(g.get("vega")),
            "iv": _f(g.get("mid_iv") or g.get("iv")),
        })

    # filter to exact expiry for safety
    contracts = [c for c in contracts if c["expiry"] == expiry]
    return {"symbol": symbol.upper(), "expiry": expiry, "contracts": contracts}