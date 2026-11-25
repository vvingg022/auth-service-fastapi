import os

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from starlette.middleware.sessions import SessionMiddleware

from .database import Base, engine
from .limiter import limiter
from .middleware import IS_PRODUCTION, SecurityHeadersMiddleware
from .routers import admin, auth, google, password

load_dotenv()

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Auth Service")

# --- Rate limiting ---
app.state.limiter = limiter


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={"detail": "Too many requests. Please try again later."},
    )


# --- CORS: only these origins may call the API from a browser ---
origins = [o.strip() for o in os.getenv("CORS_ORIGINS", "").split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

# --- Session cookie: only used to remember the OAuth "state" for 10 minutes ---
SESSION_SECRET = os.getenv("SESSION_SECRET")
if not SESSION_SECRET:
    raise RuntimeError("SESSION_SECRET is missing in .env")

app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET,
    same_site="lax",
    https_only=IS_PRODUCTION,
    max_age=600,
)

# --- Security headers on every response ---
app.add_middleware(SecurityHeadersMiddleware)

# --- Routes ---
app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(password.router)
app.include_router(google.router)


@app.get("/health")
def health():
    return {"status": "ok"}