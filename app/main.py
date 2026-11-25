import os

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

from .database import Base, engine
from .limiter import limiter
from .middleware import SecurityHeadersMiddleware
from .routers import admin, auth, password

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
    allow_credentials=True,  # needed for the refresh cookie
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

# --- Security headers on every response ---
app.add_middleware(SecurityHeadersMiddleware)

# --- Routes ---
app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(password.router)

@app.get("/health")
def health():
    return {"status": "ok"}