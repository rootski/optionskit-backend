# app/vendors/tradier.py
import httpx
import logging
from ..config import TRADIER_BASE_URL, TRADIER_API_TOKEN, TRADIER_RATE_LIMIT, ENABLE_RHO_GREEK
from .rate_limiter import RateLimiter

logger = logging.getLogger(__name__)

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

def _f_or_none(x):
    """Helper to parse float or return None (for optional fields like rho)."""
    try:
        if x is None:
            return None
        return float(x)
    except Exception:
        return None

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

    # Handle case where data or options might be None
    if not data or not isinstance(data, dict):
        logger.warning(f"Tradier API returned unexpected response: {data}")
        return {"symbol": symbol.upper(), "expiry": expiry, "contracts": []}
    
    options = data.get("options")
    if not options or not isinstance(options, dict):
        logger.warning(f"Tradier API response missing or invalid 'options' key. Response: {data}")
        return {"symbol": symbol.upper(), "expiry": expiry, "contracts": []}
    
    raw = options.get("option", []) or []
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
            # Rho is optional and vendor-provided only (Tradier provides it)
            "rho": _f_or_none(g.get("rho")) if ENABLE_RHO_GREEK else None,
        })

    # filter to exact expiry for safety
    contracts = [c for c in contracts if c["expiry"] == expiry]
    return {"symbol": symbol.upper(), "expiry": expiry, "contracts": contracts}

async def get_options_expirations_tradier(symbol: str):
    """
    Fetch available expiration dates for a specific underlying symbol from Tradier.
    Docs: GET /markets/options/expirations?symbol=...&includeAllRoots=true&strikes=true
    
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
    params = {
        "symbol": symbol.upper(),
        "includeAllRoots": "true",
        "strikes": "true"
    }

    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.get(f"{TRADIER_BASE_URL}/markets/options/expirations",
                             headers=headers, params=params)
        
        # Update rate limiter state from response headers
        _rate_limiter.update_from_headers(r.headers)
        
        r.raise_for_status()
        data = r.json()
        
        # Debug: log the raw response structure
        logger.debug(f"Tradier expirations API response for {symbol}: {data}")

    # Extract expirations and strikes from response
    # When strikes=true, structure: {"expirations": {"date": [{"expiration_date": "...", "strikes": {"strike": [...]}}]}}
    # Without strikes: {"expirations": {"date": ["2024-01-19", ...]}}
    # Handle various response structures
    dates = []
    expiration_data = []  # List of {date, strikes} objects
    
    if "expirations" in data:
        expirations = data["expirations"]
        
        # Case 1: expirations is a dict with "date" key
        if isinstance(expirations, dict):
            date_value = expirations.get("date")
            if date_value is not None:
                if isinstance(date_value, list):
                    # Check if it's a list of objects (with strikes) or strings (simple dates)
                    for item in date_value:
                        if isinstance(item, dict):
                            # Object with expiration_date and strikes
                            exp_date = item.get("expiration_date") or item.get("date")
                            strikes_obj = item.get("strikes", {})
                            strikes_list = strikes_obj.get("strike", []) if isinstance(strikes_obj, dict) else []
                            
                            # Normalize strikes to list of floats
                            if isinstance(strikes_list, list):
                                strikes = [_f(s) for s in strikes_list if s is not None]
                            elif isinstance(strikes_list, (int, float)):
                                strikes = [_f(strikes_list)]
                            else:
                                strikes = []
                            
                            if exp_date:
                                dates.append(exp_date)
                                expiration_data.append({
                                    "date": exp_date,
                                    "strikes": strikes
                                })
                        elif isinstance(item, str):
                            # Simple date string (no strikes)
                            dates.append(item)
                            expiration_data.append({
                                "date": item,
                                "strikes": []
                            })
                elif isinstance(date_value, str):
                    # Single date as string
                    dates.append(date_value)
                    expiration_data.append({
                        "date": date_value,
                        "strikes": []
                    })
            
            # Case 1b: expirations is a dict with "expiration" key (alternative structure)
            expiration_list = expirations.get("expiration")
            if expiration_list is not None:
                if isinstance(expiration_list, list):
                    # Extract dates and strikes from list of expiration objects
                    for exp in expiration_list:
                        if isinstance(exp, dict):
                            exp_date = exp.get("date") or exp.get("expiration_date")
                            strikes_obj = exp.get("strikes", {})
                            strikes_list = strikes_obj.get("strike", []) if isinstance(strikes_obj, dict) else []
                            
                            # Normalize strikes to list of floats
                            if isinstance(strikes_list, list):
                                strikes = [_f(s) for s in strikes_list if s is not None]
                            elif isinstance(strikes_list, (int, float)):
                                strikes = [_f(strikes_list)]
                            else:
                                strikes = []
                            
                            if exp_date:
                                dates.append(exp_date)
                                expiration_data.append({
                                    "date": exp_date,
                                    "strikes": strikes
                                })
                        elif isinstance(exp, str):
                            # Direct date string
                            dates.append(exp)
                            expiration_data.append({
                                "date": exp,
                                "strikes": []
                            })
                elif isinstance(expiration_list, dict):
                    # Single expiration object
                    exp_date = expiration_list.get("date") or expiration_list.get("expiration_date")
                    strikes_obj = expiration_list.get("strikes", {})
                    strikes_list = strikes_obj.get("strike", []) if isinstance(strikes_obj, dict) else []
                    
                    # Normalize strikes to list of floats
                    if isinstance(strikes_list, list):
                        strikes = [_f(s) for s in strikes_list if s is not None]
                    elif isinstance(strikes_list, (int, float)):
                        strikes = [_f(strikes_list)]
                    else:
                        strikes = []
                    
                    if exp_date:
                        dates.append(exp_date)
                        expiration_data.append({
                            "date": exp_date,
                            "strikes": strikes
                        })
        
        # Case 2: expirations is directly a list
        elif isinstance(expirations, list):
            for item in expirations:
                if isinstance(item, str):
                    dates.append(item)
                    expiration_data.append({
                        "date": item,
                        "strikes": []
                    })
    else:
        # Log if expirations key is missing
        logger.warning(f"Tradier API response missing 'expirations' key. Full response: {data}")
    
    # Filter out None, empty strings, and ensure we have a list
    dates = [d for d in dates if d and isinstance(d, str)]
    
    # If still empty, log the full response for debugging
    if not dates:
        logger.warning(f"No expirations found in response for {symbol}. Full response: {data}")
    
    return {
        "symbol": symbol.upper(),
        "expirations": dates,
        "expiration_data": expiration_data  # Includes both dates and strikes
    }


async def get_quotes_tradier(symbols: list[str]) -> list[dict]:
    """
    Fetch quotes for multiple symbols from Tradier.
    Docs: GET /markets/quotes?symbols=SYM1,SYM2,SYM3
    
    Args:
        symbols: List of symbols to fetch quotes for (comma-separated in API call)
    
    Returns:
        List of normalized quote dictionaries with fields:
        - symbol: str
        - description: str
        - last: float
        - bid: float
        - ask: float
        - volume: int
        - exchange: str (optional)
        - trade_time: str (optional)
        - change: float (optional)
        - change_percent: float (optional)
    
    Rate limiting: Automatically enforces Tradier's rate limits
    - Production: 120 requests per minute
    - Sandbox: 60 requests per minute
    """
    if not TRADIER_API_TOKEN:
        raise RuntimeError("TRADIER_API_TOKEN not set")
    
    if not symbols:
        return []
    
    # Wait if necessary to respect rate limits
    await _rate_limiter.acquire()
    
    headers = {
        "Authorization": f"Bearer {TRADIER_API_TOKEN}",
        "Accept": "application/json",
    }
    # Join symbols with comma
    symbols_str = ",".join(s.upper() for s in symbols)
    params = {"symbols": symbols_str}
    
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.get(f"{TRADIER_BASE_URL}/markets/quotes",
                             headers=headers, params=params)
        
        # Update rate limiter state from response headers
        _rate_limiter.update_from_headers(r.headers)
        
        r.raise_for_status()
        data = r.json()
    
    # Parse response structure
    # Tradier returns: {"quotes": {"quote": [...]}} or {"quotes": {"quote": {...}}} for single quote
    quotes_raw = data.get("quotes", {})
    if not quotes_raw:
        logger.warning(f"No quotes in Tradier response: {data}")
        return []
    
    quote_items = quotes_raw.get("quote", [])
    if isinstance(quote_items, dict):
        quote_items = [quote_items]
    elif not isinstance(quote_items, list):
        logger.warning(f"Unexpected quote structure: {quote_items}")
        return []
    
    # Normalize quotes
    normalized = []
    for item in quote_items:
        if not isinstance(item, dict):
            continue
        
        normalized.append({
            "symbol": (item.get("symbol") or "").upper(),
            "description": item.get("description") or "",
            "last": _f(item.get("last")),
            "bid": _f(item.get("bid")),
            "ask": _f(item.get("ask")),
            "volume": _i(item.get("volume")),
            "exchange": item.get("exchange") or "",
            "trade_time": item.get("trade_time") or "",
            "change": _f(item.get("change")),
            "change_percent": _f(item.get("change_percent")),
        })
    
    return normalized