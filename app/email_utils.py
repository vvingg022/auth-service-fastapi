import os
import smtplib
from email.message import EmailMessage

from dotenv import load_dotenv

from .logger import log_event

load_dotenv()

SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT", 2525))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
EMAIL_FROM = os.getenv("EMAIL_FROM", "no-reply@authservice.local")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")
RESET_MINUTES = int(os.getenv("RESET_TOKEN_MINUTES", 30))


def send_reset_email(to_email: str, token: str) -> None:
    link = f"{FRONTEND_URL}/reset-password?token={token}"
    body = (
        "Hello,\n\n"
        "We received a request to reset your password.\n"
        f"Use this link within {RESET_MINUTES} minutes:\n\n"
        f"{link}\n\n"
        f"Or paste this token into the reset-password endpoint:\n{token}\n\n"
        "If you did not request this, you can ignore this email.\n"
    )

    # Option A: no SMTP configured, so print to the terminal (development only)
    if not SMTP_HOST:
        print("\n[DEV ONLY - SMTP not configured] Reset email for", to_email)
        print(body)
        return

    # Option B: send through SMTP (for example Mailtrap)
    msg = EmailMessage()
    msg["Subject"] = "Reset your password"
    msg["From"] = EMAIL_FROM
    msg["To"] = to_email
    msg.set_content(body)

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)
        log_event("reset_email_sent")
    except Exception as exc:
        # Log only the error type, never credentials or the token
        log_event("reset_email_failed", "error", error=type(exc).__name__)