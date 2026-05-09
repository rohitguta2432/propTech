"""FastAPI application entrypoint."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.api import check, health
from app.config import settings
from app.middleware.rate_limit import limiter, rate_limit_exception_handler

# Import scraper modules so each registers itself with the router.
# (Side-effect imports — order doesn't matter; each calls register() at module load.)
from app.scrapers import acres99, magicbricks  # noqa: F401

app = FastAPI(
    title="PropCheck API",
    description="Trust layer for Indian property listings.",
    version=settings.app_version,
)

# Rate limiter — see app/middleware/rate_limit.py and specs/rate-limiting.md.
# slowapi looks up the configured limiter via app.state.limiter; the
# middleware enforces the per-route limits and the handler renders 429.
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exception_handler)
app.add_middleware(SlowAPIMiddleware)

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
