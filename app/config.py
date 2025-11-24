# app/config.py
import os
from dotenv import load_dotenv
load_dotenv()  # loads .env in dev; in AWS we use env vars & Secrets Manager

# Massive (Polygon) – optional for later
MASSIVE_BASE_URL = os.getenv("MASSIVE_BASE_URL", "https://api.polygon.io")
MASSIVE_API_KEY  = os.getenv("MASSIVE_API_KEY", "")

# Tradier (Production API)
TRADIER_BASE_URL  = os.getenv("TRADIER_BASE_URL", "https://api.tradier.com/v1")
TRADIER_API_TOKEN = os.getenv("TRADIER_API_TOKEN", "")

# Detect if using sandbox (sandbox has lower rate limits)
TRADIER_IS_SANDBOX = "sandbox" in TRADIER_BASE_URL.lower()
TRADIER_RATE_LIMIT = 60 if TRADIER_IS_SANDBOX else 120  # 60 for sandbox, 120 for production

# CORS
ALLOW_ORIGINS = os.getenv("ALLOW_ORIGINS", "*")

# Quotes snapshot service configuration
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "860"))
REFRESH_INTERVAL_SEC = int(os.getenv("REFRESH_INTERVAL_SEC", "61"))
MAX_CONCURRENCY = int(os.getenv("MAX_CONCURRENCY", "8"))

# Rho Greek feature flag (default: enabled)
ENABLE_RHO_GREEK = os.getenv("ENABLE_RHO_GREEK", "true").lower() == "true"