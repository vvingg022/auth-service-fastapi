from fastapi import FastAPI

from .database import Base, engine
from .routers import auth

# Creates the tables (and auth.db) if they don't exist yet
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Auth Service")

app.include_router(auth.router)


@app.get("/health")
def health():
    return {"status": "ok"}