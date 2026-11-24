import logging
import os
from logging.handlers import RotatingFileHandler

os.makedirs("logs", exist_ok=True)

security_logger = logging.getLogger("security")
security_logger.setLevel(logging.INFO)

if not security_logger.handlers:
    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")

    # File: rotates at 1 MB and keeps 3 old files
    file_handler = RotatingFileHandler(
        "logs/security.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)

    # Console: so you also see events in the terminal
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    security_logger.addHandler(file_handler)
    security_logger.addHandler(console_handler)
    security_logger.propagate = False


def log_event(event: str, level: str = "info", **fields):
    """Example: log_event("login_failed", "warning", user_id=3, ip="1.2.3.4")"""
    details = " ".join(f"{key}={value}" for key, value in fields.items())
    getattr(security_logger, level)(f"{event} {details}".strip())