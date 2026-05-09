"""FastAPI application entrypoint."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import check, health
from app.config import settings

app = FastAPI(
    title="PropCheck API",
    description="Trust layer for Indian property listings.",
    version=settings.app_version,
)

# CORS — locked down later, open for local dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# Routers
app.include_router(health.router, tags=["health"])
app.include_router(check.router, prefix="/v1", tags=["check"])


@app.get("/")
def root() -> dict[str, str]:
    return {
        "name": "PropCheck API",
        "version": settings.app_version,
        "docs": "/docs",
    }
