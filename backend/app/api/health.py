"""Liveness probe."""
import time

from fastapi import APIRouter

from app.config import settings

router = APIRouter()

# Captured once at module import — close enough to "process start" for a
# liveness probe.
_START_TIME = time.time()


@router.get("/healthz")
def healthz() -> dict[str, object]:
    return {
        "status": "ok",
        "version": settings.app_version,
        "uptime_s": int(time.time() - _START_TIME),
    }
