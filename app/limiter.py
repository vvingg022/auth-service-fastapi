from slowapi import Limiter
from slowapi.util import get_remote_address

# Counts requests per client IP address
limiter = Limiter(key_func=get_remote_address)