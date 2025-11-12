# app/routes/quotes_snapshot.py
import logging
from fastapi import APIRouter, Query, HTTPException

from ..services.snapshot_quotes import get_snapshot, get_last_update, get_background_task_status
from ..services.occ_symbols import get_symbol_count

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/v1/markets/quotes/snapshot")
async def quotes_snapshot(symbols: str = Query(None, description="Comma-separated list of symbols to filter by. If not provided, returns all quotes.")):
    """
    Get the current quotes snapshot for all optionable underlyings.
    Returns the most recent snapshot with last_update, count, and results.
    
    Query Parameters:
        symbols: Optional comma-separated list of symbols (e.g., "AAPL,MSFT,GOOGL").
                 If not provided, returns quotes for all symbols.
    
    Examples:
        GET /v1/markets/quotes/snapshot                    # Returns all quotes
        GET /v1/markets/quotes/snapshot?symbols=AAPL       # Returns only AAPL
        GET /v1/markets/quotes/snapshot?symbols=AAPL,MSFT  # Returns AAPL and MSFT
    """
    try:
        # Parse comma-separated symbols if provided
        symbol_list = None
        if symbols:
            symbol_list = [s.strip().upper() for s in symbols.split(",") if s.strip()]
        
        return get_snapshot(symbols=symbol_list)
    except Exception as e:
        logger.error(f"Error retrieving quotes snapshot: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve quotes snapshot: {e}")


@router.get("/v1/markets/quotes/last_update")
async def quotes_last_update():
    """
    Get the last update timestamp and count for the quotes snapshot.
    Lightweight endpoint to check snapshot freshness.
    """
    try:
        return get_last_update()
    except Exception as e:
        logger.error(f"Error retrieving quotes last update: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve quotes last update: {e}")


@router.get("/v1/markets/quotes/diagnostic")
async def quotes_diagnostic():
    """
    Diagnostic endpoint to check the status of the quotes snapshot service.
    Useful for debugging why quotes might not be available.
    """
    try:
        task_status = get_background_task_status()
        occ_symbol_count = get_symbol_count()
        snapshot_info = get_last_update()
        
        return {
            "background_task": task_status,
            "occ_symbols": {
                "count": occ_symbol_count,
                "available": occ_symbol_count > 0
            },
            "snapshot": snapshot_info,
            "status": "healthy" if (task_status.get("running") and snapshot_info.get("count", 0) > 0) else "degraded"
        }
    except Exception as e:
        logger.error(f"Error retrieving quotes diagnostic: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve quotes diagnostic: {e}")

