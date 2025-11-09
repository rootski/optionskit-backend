# app/main.py
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from .config import ALLOW_ORIGINS, MASSIVE_API_KEY, TRADIER_API_TOKEN
from .vendors.tradier import get_option_chain_tradier, get_options_expirations_tradier
from .vendors.massive import get_option_chain_snapshot  # fallback vendor
from .version import get_version_info
from .services.occ_symbols import refresh_symbols, get_symbols, get_symbol_count, get_last_update as get_occ_last_update

logger = logging.getLogger(__name__)

# Global scheduler instance
scheduler = AsyncIOScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan: startup and shutdown."""
    # Startup: Initialize symbols and start scheduler
    logger.info("Starting up: Initializing OCC symbols...")
    try:
        await refresh_symbols()
        logger.info(f"Initialized {get_symbol_count()} symbols on startup")
    except Exception as e:
        logger.error(f"Failed to initialize symbols on startup: {e}")
    
    # Start scheduler to refresh symbols daily at 2 AM UTC
    scheduler.add_job(
        refresh_symbols,
        trigger=CronTrigger(hour=2, minute=0),  # Daily at 2 AM UTC
        id="refresh_occ_symbols",
        name="Refresh OCC symbols daily",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("Scheduler started: OCC symbols will refresh daily at 2 AM UTC")
    
    yield
    
    # Shutdown: Stop scheduler
    logger.info("Shutting down: Stopping scheduler...")
    scheduler.shutdown(wait=False)


app = FastAPI(title="Options Backend", version="0.2.0", lifespan=lifespan)

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
    """Returns the deployed version information including git SHA, tag, and OCC symbols last update."""
    occ_last_update = get_occ_last_update()
    return get_version_info(occ_last_update=occ_last_update)

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

@app.get("/v1/markets/options/expirations")
async def expirations(symbol: str = Query(...)):
    """
    Get available expiration dates for a specific underlying symbol.
    Returns expirations with includeAllRoots=true and strikes=true as per Tradier API.
    """
    try:
        return await get_options_expirations_tradier(symbol)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch expirations: {e}")

@app.get("/v1/markets/options/symbols")
async def get_options_symbols():
    """
    Get the set of all underlying symbols that have options available.
    Returns a Python set (as a list in JSON) of unique symbols.
    Symbols are refreshed daily from OCC (Options Clearing Corporation).
    """
    try:
        symbols = get_symbols()
        last_update = get_occ_last_update()
        
        return {
            "symbols": sorted(list(symbols)),  # Convert set to sorted list for JSON
            "count": len(symbols),
            "last_update": last_update.isoformat() if last_update else None,
            "note": "This is a Python set (enforced uniqueness). Returned as sorted list for JSON compatibility."
        }
    except Exception as e:
        logger.error(f"Error retrieving symbols: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve symbols: {e}")

@app.post("/v1/markets/options/symbols/refresh")
async def refresh_options_symbols():
    """
    Manually trigger a refresh of the options symbols from OCC.
    Normally this runs automatically daily at 2 AM UTC.
    """
    try:
        await refresh_symbols(raise_on_error=True)
        symbols = get_symbols()
        last_update = get_occ_last_update()
        
        return {
            "status": "success",
            "count": len(symbols),
            "last_update": last_update.isoformat() if last_update else None,
            "message": f"Successfully refreshed {len(symbols)} symbols"
        }
    except Exception as e:
        logger.error(f"Error refreshing symbols: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to refresh symbols: {e}")