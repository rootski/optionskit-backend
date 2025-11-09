"""
Version information for the API.
Can be set via environment variables at build/deploy time, or read from git.
"""
import os
import subprocess
from typing import Optional
from datetime import datetime


def get_git_sha() -> str:
    """Get the current git commit SHA (short)."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            timeout=2
        )
        return result.stdout.strip()
    except (subprocess.SubprocessError, FileNotFoundError, subprocess.TimeoutExpired):
        return os.getenv("GIT_SHA", "unknown")


def get_git_tag() -> Optional[str]:
    """Get the current git tag (if any)."""
    try:
        result = subprocess.run(
            ["git", "describe", "--tags", "--always"],
            capture_output=True,
            text=True,
            check=True,
            timeout=2
        )
        tag = result.stdout.strip()
        # If it's just a commit hash, return None (no tag)
        if tag.startswith("v") or "-" in tag:
            return tag
        return None
    except (subprocess.SubprocessError, FileNotFoundError, subprocess.TimeoutExpired):
        env_tag = os.getenv("GIT_TAG")
        return env_tag if env_tag else None


def get_version() -> str:
    """Get the version number from environment or default."""
    return os.getenv("API_VERSION", "0.2.0")


def get_version_info(occ_last_update: datetime | None = None) -> dict:
    """
    Get complete version information.
    
    Args:
        occ_last_update: Optional timestamp of last OCC symbols update
    """
    info = {
        "version": get_version(),
        "git_sha": get_git_sha(),
        "git_tag": get_git_tag(),
    }
    
    # Add OCC last update timestamp if provided
    if occ_last_update:
        info["occ_symbols_last_update"] = occ_last_update.isoformat()
    else:
        info["occ_symbols_last_update"] = None
    
    return info

