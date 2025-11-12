# app/services/snapshot_quotes.py
"""
Background service to periodically fetch and store quotes for all optionable underlyings.
Refreshes every REFRESH_INTERVAL_SEC seconds by fetching quotes in batches from Tradier.
"""
import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional

from ..config import BATCH_SIZE, REFRESH_INTERVAL_SEC, MAX_CONCURRENCY
from ..vendors.tradier import get_quotes_tradier
from .occ_symbols import get_symbols

logger = logging.getLogger(__name__)

# In-memory storage for quotes snapshot
SNAPSHOT: Dict = {
    "last_update": None,  # datetime
    "results": [],  # List[dict] with {symbol, description, last, bid, ask, volume}
    "by_symbol": {},  # Dict[str, dict] for quick lookup
    "count": 0
}

# Background task reference
_background_task: Optional[asyncio.Task] = None


def _chunk_list(items: List, chunk_size: int) -> List[List]:
    """Split a list into chunks of specified size."""
    for i in range(0, len(items), chunk_size):
        yield items[i:i + chunk_size]


async def _fetch_quotes_batch(symbols_batch: List[str]) -> List[dict]:
    """
    Fetch quotes for a single batch of symbols.
    
    Args:
        symbols_batch: List of symbols to fetch
    
    Returns:
        List of normalized quote dictionaries
    """
    try:
        quotes = await get_quotes_tradier(symbols_batch)
        return quotes
    except Exception as e:
        logger.error(f"Error fetching quotes for batch {symbols_batch[:5]}...: {e}")
        return []  # Return empty list on error, don't fail entire cycle


async def _refresh_quotes_snapshot() -> bool:
    """
    Refresh the quotes snapshot by fetching quotes for all symbols.
    
    Returns:
        True if refresh was successful, False otherwise
    """
    try:
        # Get current symbol list from OCC service
        symbols = get_symbols()
        symbols_list = sorted(list(symbols))
        
        if not symbols_list:
            logger.warning("No symbols available for quotes snapshot")
            return False
        
        logger.info(f"Starting quotes snapshot refresh for {len(symbols_list)} symbols")
        
        # Chunk symbols into batches
        batches = list(_chunk_list(symbols_list, BATCH_SIZE))
        logger.info(f"Split into {len(batches)} batches of up to {BATCH_SIZE} symbols each")
        
        # Fetch quotes with controlled concurrency
        semaphore = asyncio.Semaphore(MAX_CONCURRENCY)
        
        async def fetch_with_semaphore(batch: List[str]) -> List[dict]:
            async with semaphore:
                return await _fetch_quotes_batch(batch)
        
        # Fetch all batches concurrently (with semaphore limiting)
        tasks = [fetch_with_semaphore(batch) for batch in batches]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Collect all quotes, handling exceptions
        all_quotes = []
        errors = 0
        
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Batch {i+1}/{len(batches)} failed: {result}")
                errors += 1
            elif isinstance(result, list):
                all_quotes.extend(result)
            else:
                logger.warning(f"Unexpected result type from batch {i+1}: {type(result)}")
                errors += 1
        
        if errors > 0:
            logger.warning(f"Completed with {errors} batch errors out of {len(batches)} batches")
        
        # Filter to only include required fields for snapshot
        snapshot_quotes = []
        for quote in all_quotes:
            snapshot_quotes.append({
                "symbol": quote.get("symbol", ""),
                "description": quote.get("description", ""),
                "last": quote.get("last", 0.0),
                "bid": quote.get("bid", 0.0),
                "ask": quote.get("ask", 0.0),
                "volume": quote.get("volume", 0),
            })
        
        # Build by_symbol lookup
        by_symbol = {q["symbol"]: q for q in snapshot_quotes}
        
        # Only update snapshot if we got some results
        if snapshot_quotes:
            global SNAPSHOT
            SNAPSHOT = {
                "last_update": datetime.now(),
                "results": snapshot_quotes,
                "by_symbol": by_symbol,
                "count": len(snapshot_quotes)
            }
            logger.info(f"Quotes snapshot updated: {len(snapshot_quotes)} quotes, {len(symbols_list)} symbols requested")
            return True
        else:
            logger.error("No quotes retrieved - keeping previous snapshot")
            return False
            
    except Exception as e:
        logger.error(f"Error refreshing quotes snapshot: {e}", exc_info=True)
        return False


async def _background_refresh_loop():
    """
    Background task that periodically refreshes the quotes snapshot.
    Runs every REFRESH_INTERVAL_SEC seconds.
    Does an immediate refresh on startup to ensure APIs work quickly.
    """
    logger.info(f"Starting quotes snapshot background refresh loop (interval: {REFRESH_INTERVAL_SEC}s)")
    
    # Wait a bit for OCC symbols to be initialized on startup
    await asyncio.sleep(1)
    
    # Do immediate refresh on startup
    try:
        logger.info("Performing initial quotes snapshot refresh on startup")
        success = await _refresh_quotes_snapshot()
        if not success:
            logger.warning("Initial quotes snapshot refresh failed - keeping empty snapshot")
    except Exception as e:
        logger.error(f"Unexpected error in initial refresh: {e}", exc_info=True)
    
    # Then enter periodic refresh loop
    while True:
        try:
            success = await _refresh_quotes_snapshot()
            if not success:
                logger.warning("Quotes snapshot refresh failed - keeping previous snapshot")
        except Exception as e:
            logger.error(f"Unexpected error in background refresh loop: {e}", exc_info=True)
        
        # Wait for next cycle
        await asyncio.sleep(REFRESH_INTERVAL_SEC)


def start_background_task():
    """
    Start the background refresh task.
    Should be called during FastAPI startup.
    """
    global _background_task
    if _background_task is None or _background_task.done():
        _background_task = asyncio.create_task(_background_refresh_loop())
        logger.info("Quotes snapshot background task started")
    else:
        logger.warning("Background task already running")


def stop_background_task():
    """
    Stop the background refresh task.
    Should be called during FastAPI shutdown.
    """
    global _background_task
    if _background_task and not _background_task.done():
        _background_task.cancel()
        logger.info("Quotes snapshot background task cancelled")


def get_snapshot(symbols: Optional[List[str]] = None) -> Dict:
    """
    Get the current quotes snapshot, optionally filtered by symbols.
    
    Args:
        symbols: Optional list of symbols to filter by. If None, returns all quotes.
    
    Returns:
        Dictionary with last_update, count, and results (filtered if symbols provided)
    """
    if symbols is None or len(symbols) == 0:
        # Return all quotes
        results = SNAPSHOT["results"]
        count = SNAPSHOT["count"]
    else:
        # Filter by requested symbols using the by_symbol lookup
        symbols_upper = [s.upper() for s in symbols]
        results = []
        for symbol in symbols_upper:
            if symbol in SNAPSHOT["by_symbol"]:
                results.append(SNAPSHOT["by_symbol"][symbol])
        count = len(results)
    
    return {
        "last_update": SNAPSHOT["last_update"].isoformat() if SNAPSHOT["last_update"] else None,
        "count": count,
        "results": results
    }


def get_last_update() -> Dict:
    """
    Get just the last update timestamp and count.
    
    Returns:
        Dictionary with last_update and count
    """
    return {
        "last_update": SNAPSHOT["last_update"].isoformat() if SNAPSHOT["last_update"] else None,
        "count": SNAPSHOT["count"]
    }

