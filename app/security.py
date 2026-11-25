import os
from datetime import datetime, timedelta, timezone
import secrets
import bcrypt
import jwt
from dotenv import load_dotenv

load_dotenv()

ACCESS_SECRET = os.getenv("JWT_ACCESS_SECRET")
REFRESH_SECRET = os.getenv("JWT_REFRESH_SECRET")
ACCESS_MINUTES = int(os.getenv("ACCESS_EXPIRE_MINUTES", 15))
REFRESH_DAYS = int(os.getenv("REFRESH_EXPIRE_DAYS", 7))
ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))


def create_access_token(user_id: int, role: str) -> str:
    payload = {
        "sub": str(user_id),
        "role": role,
        "jti": secrets.token_hex(16),
        "exp": datetime.now(timezone.utc) + timedelta(minutes=ACCESS_MINUTES),
    }
    return jwt.encode(payload, ACCESS_SECRET, algorithm=ALGORITHM)


def create_refresh_token(user_id: int) -> str:
    payload = {
        "sub": str(user_id),
        "jti": secrets.token_hex(16),
        "exp": datetime.now(timezone.utc) + timedelta(days=REFRESH_DAYS),
    }
    return jwt.encode(payload, REFRESH_SECRET, algorithm=ALGORITHM)

def decode_access_token(token: str) -> dict:
    return jwt.decode(token, ACCESS_SECRET, algorithms=[ALGORITHM])


def decode_refresh_token(token: str) -> dict:
    return jwt.decode(token, REFRESH_SECRET, algorithms=[ALGORITHM])