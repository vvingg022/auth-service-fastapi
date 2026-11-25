import os

# These MUST be set before the app is imported
os.environ["DATABASE_URL"] = "sqlite:///./test_auth.db"
os.environ["JWT_ACCESS_SECRET"] = "test-access-secret-0123456789abcdef0123456789abcdef"
os.environ["JWT_REFRESH_SECRET"] = "test-refresh-secret-0123456789abcdef0123456789abcdef"
os.environ["SESSION_SECRET"] = "test-session-secret-0123456789abcdef0123456789abcdef"
os.environ["CORS_ORIGINS"] = "http://localhost:3000"
os.environ["SMTP_HOST"] = ""  # never send real emails from tests

import pytest
from fastapi.testclient import TestClient

from app import models, security
from app.database import Base, SessionLocal, engine
from app.limiter import limiter
from app.main import app


@pytest.fixture(autouse=True)
def fresh_db():
    """Runs before EVERY test: empty database, rate limiting off."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    limiter.enabled = False
    yield


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def make_user():
    """Creates a user straight in the database and returns its id."""

    def _make(email="user@test.com", password="Test12345", role="user", name="Test User"):
        db = SessionLocal()
        try:
            user = models.User(
                name=name,
                email=email,
                password_hash=security.hash_password(password),
                role=role,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            return user.id
        finally:
            db.close()

    return _make


@pytest.fixture
def login(client):
    def _login(email="user@test.com", password="Test12345"):
        return client.post("/api/auth/login", json={"email": email, "password": password})

    return _login


@pytest.fixture
def auth_header(login):
    """Logs in and returns {"Authorization": "Bearer ..."} ready to use."""

    def _header(email="user@test.com", password="Test12345"):
        response = login(email, password)
        return {"Authorization": f"Bearer {response.json()['access_token']}"}

    return _header


@pytest.fixture
def rate_limit_on():
    """Only used by the rate-limit test."""
    limiter.enabled = True
    limiter.reset()
    yield
    limiter.enabled = False
    limiter.reset()