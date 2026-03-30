# app/services/snapshot_quotes.py
"""
Background service to periodically fetch and store quotes for all optionable underlyings.
Refreshes every REFRESH_INTERVAL_SEC seconds by fetching quotes in batches from Tradier.
Snapshot is persisted in Redis so it survives process restarts and is shared across instances.
"""
import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional

from ..config import BATCH_SIZE, REFRESH_INTERVAL_SEC, MAX_CONCURRENCY, SNAPSHOT_TTL
from ..redis_client import get_redis
from ..vendors.tradier import get_quotes_tradier
from .occ_symbols import get_symbols

logger = logging.getLogger(__name__)

_KEY_RESULTS      = "optionskit:snapshot:results"
_KEY_LAST_UPDATE  = "optionskit:snapshot:last_update"
_KEY_COUNT        = "optionskit:snapshot:count"

# Background task reference
_background_task: Optional[asyncio.Task] = None


def _chunk_list(items: List, chunk_size: int) -> List[List]:
    """Split a list into chunks of specified size."""
    for i in range(0, len(items), chunk_size):
        yield items[i:i + chunk_size]


async def _fetch_quotes_batch(symbols_batch: List[str]) -> List[dict]:
    try:
        return await get_quotes_tradier(symbols_batch)
    except Exception as e:
        logger.error(f"Error fetching quotes for batch {symbols_batch[:5]}...: {e}")
        return []


async def _write_snapshot_to_redis(quotes: List[dict], now: datetime) -> None:
    """Write snapshot atomically using a pipeline."""
    redis = get_redis()
    pipe = redis.pipeline()
    pipe.set(_KEY_RESULTS,     json.dumps(quotes),   ex=SNAPSHOT_TTL)
    pipe.set(_KEY_LAST_UPDATE, now.isoformat(),       ex=SNAPSHOT_TTL)
    pipe.set(_KEY_COUNT,       str(len(quotes)),      ex=SNAPSHOT_TTL)
    await pipe.execute()


async def _read_snapshot_from_redis() -> Dict:
    """Read snapshot from Redis. Returns empty structure if keys are missing."""
    redis = get_redis()
    results_json, last_update_str, count_str = await asyncio.gather(
        redis.get(_KEY_RESULTS),
        redis.get(_KEY_LAST_UPDATE),
        redis.get(_KEY_COUNT),
    )
    results     = json.loads(results_json) if results_json else []
    last_update = datetime.fromisoformat(last_update_str) if last_update_str else None
    count       = int(count_str) if count_str else 0
    by_symbol   = {q["symbol"]: q for q in results}
    return {"last_update": last_update, "results": results, "by_symbol": by_symbol, "count": count}


async def _refresh_quotes_snapshot() -> bool:
    """
    Refresh the quotes snapshot by fetching quotes for all symbols.

    Returns:
        True if refresh was successful, False otherwise
    """
    try:
        symbols = get_symbols()
        symbols_list = sorted(list(symbols))

        if not symbols_list:
            logger.warning("No symbols available for quotes snapshot")
            return False

        logger.info(f"Starting quotes snapshot refresh for {len(symbols_list)} symbols")

        batches = list(_chunk_list(symbols_list, BATCH_SIZE))
        logger.info(f"Split into {len(batches)} batches of up to {BATCH_SIZE} symbols each")

        semaphore = asyncio.Semaphore(MAX_CONCURRENCY)

        async def fetch_with_semaphore(batch: List[str]) -> List[dict]:
            async with semaphore:
                return await _fetch_quotes_batch(batch)

        tasks = [fetch_with_semaphore(batch) for batch in batches]
        results = await asyncio.gather(*tasks, return_exceptions=True)

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

        snapshot_quotes = [
            {
                "symbol":      q.get("symbol", ""),
                "description": q.get("description", ""),
                "last":        q.get("last", 0.0),
                "bid":         q.get("bid", 0.0),
                "ask":         q.get("ask", 0.0),
                "volume":      q.get("volume", 0),
            }
            for q in all_quotes
        ]

        if snapshot_quotes:
            now = datetime.now()
            await _write_snapshot_to_redis(snapshot_quotes, now)
            logger.info(f"Quotes snapshot written to Redis: {len(snapshot_quotes)} quotes, {len(symbols_list)} symbols requested")
            return True
        else:
            logger.error("No quotes retrieved — keeping existing Redis snapshot")
            return False

    except Exception as e:
        logger.error(f"Error refreshing quotes snapshot: {e}", exc_info=True)
        return False


async def _background_refresh_loop():
    """
    Background task that periodically refreshes the quotes snapshot.
    Runs every REFRESH_INTERVAL_SEC seconds.
    Does an immediate refresh on startup to ensure data is available quickly.
    """
    logger.info(f"Starting quotes snapshot background refresh loop (interval: {REFRESH_INTERVAL_SEC}s)")

    # Wait for OCC symbols to be initialized on startup
    max_wait_attempts = 10
    symbols_ready = False
    for attempt in range(max_wait_attempts):
        symbols = get_symbols()
        if len(symbols) > 0:
            symbols_ready = True
            logger.info(f"OCC symbols ready: {len(symbols)} symbols available (waited {attempt} seconds)")
            break
        logger.info(f"Waiting for OCC symbols to be initialized... (attempt {attempt + 1}/{max_wait_attempts})")
        await asyncio.sleep(1)

    if not symbols_ready:
        logger.error("OCC symbols not available after waiting — quotes snapshot may be empty")

    # Do immediate refresh on startup
    try:
        logger.info("Performing initial quotes snapshot refresh on startup")
        success = await _refresh_quotes_snapshot()
        if success:
            count_str = await get_redis().get(_KEY_COUNT)
            logger.info(f"Initial quotes snapshot refresh successful: {count_str} quotes loaded")
        else:
            logger.warning("Initial quotes snapshot refresh failed — keeping existing Redis snapshot")
    except Exception as e:
        logger.error(f"Unexpected error in initial refresh: {e}", exc_info=True)

    # Periodic refresh loop
    while True:
        try:
            success = await _refresh_quotes_snapshot()
            if success:
                count_str = await get_redis().get(_KEY_COUNT)
                logger.info(f"Quotes snapshot refresh successful: {count_str} quotes")
            else:
                logger.warning("Quotes snapshot refresh failed — keeping previous Redis snapshot")
        except Exception as e:
            logger.error(f"Unexpected error in background refresh loop: {e}", exc_info=True)

        await asyncio.sleep(REFRESH_INTERVAL_SEC)


def start_background_task():
    """Start the background refresh task. Called during FastAPI startup."""
    global _background_task
    try:
        if _background_task is None or _background_task.done():
            loop = asyncio.get_event_loop()
            _background_task = loop.create_task(_background_refresh_loop())
            logger.info("Quotes snapshot background task created and started")
        else:
            logger.warning("Background task already running")
    except RuntimeError as e:
        logger.warning(f"No event loop found, attempting to create one: {e}")
        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            _background_task = loop.create_task(_background_refresh_loop())
            logger.info("Quotes snapshot background task created with new event loop")
        except Exception as e2:
            logger.error(f"Failed to start background task: {e2}", exc_info=True)
    except Exception as e:
        logger.error(f"Failed to start background task: {e}", exc_info=True)


def stop_background_task():
    """Stop the background refresh task. Called during FastAPI shutdown."""
    global _background_task
    if _background_task and not _background_task.done():
        _background_task.cancel()
        logger.info("Quotes snapshot background task cancelled")


async def get_snapshot(symbols: Optional[List[str]] = None) -> Dict:
    """
    Get the current quotes snapshot from Redis, optionally filtered by symbols.

    Args:
        symbols: Optional list of symbols to filter by. If None, returns all quotes.

    Returns:
        Dictionary with last_update, count, and results.
    """
    snap = await _read_snapshot_from_redis()

    if symbols is None or len(symbols) == 0:
        results = snap["results"]
        count   = snap["count"]
    else:
        symbols_upper = [s.upper() for s in symbols]
        results = [snap["by_symbol"][s] for s in symbols_upper if s in snap["by_symbol"]]
        count   = len(results)

    return {
        "last_update": snap["last_update"].isoformat() if snap["last_update"] else None,
        "count":       count,
        "results":     results,
    }


async def get_last_update() -> Dict:
    """
    Get just the last update timestamp and count from Redis.
    Lightweight endpoint to check snapshot freshness.
    """
    redis = get_redis()
    last_update_str, count_str = await asyncio.gather(
        redis.get(_KEY_LAST_UPDATE),
        redis.get(_KEY_COUNT),
    )
    return {
        "last_update": last_update_str if last_update_str else None,
        "count":       int(count_str) if count_str else 0,
    }


def get_background_task_status() -> Dict:
    """
    Get the status of the background refresh task.
    Synchronous — only inspects the asyncio.Task object.
    """
    global _background_task
    status = {
        "running":   False,
        "done":      False,
        "cancelled": False,
        "exception": None,
    }

    if _background_task is None:
        status["running"] = False
        status["message"] = "Background task not started"
    else:
        status["running"]   = not _background_task.done()
        status["done"]      = _background_task.done()
        status["cancelled"] = _background_task.cancelled()

        if _background_task.done():
            try:
                _background_task.exception()
            except Exception as e:
                status["exception"] = str(e)
            status["message"] = "Background task completed" if not _background_task.cancelled() else "Background task cancelled"
        else:
            status["message"] = "Background task is running"

    return status
