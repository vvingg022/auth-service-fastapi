import os

from slowapi import Limiter
from slowapi.util import get_remote_address

# Set RATE_LIMIT_ENABLED=false ONLY for local load testing
RATE_LIMIT_ENABLED = os.getenv("RATE_LIMIT_ENABLED", "true").lower() != "false"

limiter = Limiter(key_func=get_remote_address, enabled=RATE_LIMIT_ENABLED)