# app/services/occ_symbols.py
"""
Service to download, parse, and store OCC (Options Clearing Corporation) 
equity symbols that have options available.

Downloads from: https://marketdata.theocc.com/delo-download?prodType=ALL&downloadFields=US;OS;SN;EXCH;PL;ONN&format=txt
"""
import httpx
import logging
from typing import Set
from datetime import datetime

logger = logging.getLogger(__name__)

# In-memory storage for symbols
_symbols: Set[str] = set()
_last_update: datetime | None = None
_occ_url = "https://marketdata.theocc.com/delo-download?prodType=ALL&downloadFields=US;OS;SN;EXCH;PL;ONN&format=txt"


async def fetch_and_parse_occ_symbols() -> Set[str]:
    """
    Download and parse the OCC text file to extract underlying symbols.
    
    Returns:
        Set of unique underlying symbols (second column from the file)
    """
    symbols = set()
    
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            logger.info(f"Downloading OCC symbols from {_occ_url}")
            response = await client.get(_occ_url)
            response.raise_for_status()
            
            # Parse the text file
            # Format: tab-separated or space-separated with symbol in second column
            # Example: "1AAL  	AAL   	American Airlines Group, Inc. (AMER/FLEX)	ABCPX	25000000	EF"
            content = response.text
            lines = content.strip().split('\n')
            
            logger.info(f"Parsing {len(lines)} lines from OCC file")
            
            for line_num, line in enumerate(lines, start=1):
                if not line.strip():
                    continue
                
                # Try tab-separated first (most common format)
                parts = line.split('\t')
                
                # If tab-split didn't work well, try splitting by multiple spaces
                if len(parts) < 2 or (len(parts) == 1 and '\t' not in line):
                    # Split by whitespace and filter out empty strings
                    parts = [p for p in line.split() if p]
                    if len(parts) < 2:
                        logger.debug(f"Skipping line {line_num}: insufficient columns - {line[:50]}")
                        continue
                
                # Extract second column (index 1) - the underlying symbol
                symbol = parts[1].strip()
                
                # Clean up symbol (remove any non-alphanumeric characters)
                symbol = ''.join(c for c in symbol if c.isalnum())
                
                # Validate symbol (should be 1-4 characters, alphanumeric)
                if symbol and 1 <= len(symbol) <= 4:
                    symbols.add(symbol.upper())
                else:
                    logger.debug(f"Skipping invalid symbol on line {line_num}: {symbol} (original: {parts[1] if len(parts) > 1 else 'N/A'})")
            
            logger.info(f"Successfully parsed {len(symbols)} unique symbols from OCC file")
            return symbols
            
    except httpx.HTTPError as e:
        logger.error(f"HTTP error downloading OCC symbols: {e}")
        raise
    except Exception as e:
        logger.error(f"Error parsing OCC symbols: {e}")
        raise


async def refresh_symbols(raise_on_error: bool = False) -> None:
    """
    Refresh the stored symbols by downloading and parsing the OCC file.
    Updates the in-memory storage.
    
    Args:
        raise_on_error: If True, raise exception on failure. If False, log error and keep existing symbols.
    """
    try:
        new_symbols = await fetch_and_parse_occ_symbols()
        global _symbols, _last_update
        
        _symbols = new_symbols
        _last_update = datetime.now()
        
        logger.info(f"Symbols refreshed: {len(_symbols)} unique symbols stored")
    except Exception as e:
        logger.error(f"Failed to refresh symbols: {e}")
        if raise_on_error:
            raise
        # Otherwise, keep existing symbols if refresh fails
        # This allows the service to continue operating with stale data


def get_symbols() -> Set[str]:
    """
    Get the current set of symbols.
    
    Returns:
        Set of unique underlying symbols
    """
    return _symbols.copy()  # Return a copy to prevent external modification


def get_symbol_count() -> int:
    """Get the count of stored symbols."""
    return len(_symbols)


def get_last_update() -> datetime | None:
    """Get the timestamp of the last successful update."""
    return _last_update


def is_symbol_available(symbol: str) -> bool:
    """
    Check if a symbol is available in the stored set.
    
    Args:
        symbol: Symbol to check (case-insensitive)
    
    Returns:
        True if symbol is in the set, False otherwise
    """
    return symbol.upper() in _symbols

