# app/main.py
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .config import ALLOW_ORIGINS, MASSIVE_API_KEY, TRADIER_API_TOKEN
from .vendors.tradier import get_option_chain_tradier
from .vendors.massive import get_option_chain_snapshot  # fallback vendor
from .version import get_version_info

app = FastAPI(title="Options Backend", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in ALLOW_ORIGINS.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/healthz")
def healthz():
    return {"ok": True}

@app.get("/healthz/secrets")
def secrets_health():
    return {
        "tradier_token_set": bool(TRADIER_API_TOKEN)
    }

@app.get("/version")
def version():
    """Returns the deployed version information including git SHA and tag."""
    return get_version_info()

@app.get("/v1/markets/chain")
async def chain(symbol: str = Query(...), expiry: str = Query(...)):
    # 1) Try Tradier first (default vendor)
    tradier_err = None
    try:
        return await get_option_chain_tradier(symbol, expiry)
    except Exception as e:
        tradier_err = e

    # 2) Fallback to Massive/Polygon if Tradier fails
    if MASSIVE_API_KEY and MASSIVE_API_KEY != "REPLACE_ME":
        try:
            return await get_option_chain_snapshot(symbol, expiry)
        except Exception as massive_err:
            # Both vendors failed - report both errors for debugging
            error_detail = f"Tradier failed: {tradier_err}. Massive fallback failed: {massive_err}"
            raise HTTPException(status_code=502, detail=error_detail)
    
    # Tradier failed and no valid Massive API key
    if tradier_err:
        raise HTTPException(status_code=502, detail=f"Tradier failed: {tradier_err}")
    
    raise HTTPException(status_code=502, detail="Chain fetch failed: unknown error")