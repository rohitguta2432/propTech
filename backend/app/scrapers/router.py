"""Map a parsed URL to the right portal scraper.

Mirrors `app/parsers/router.py` but for full HTML scraping.
"""
from __future__ import annotations

from typing import Callable

from app.scrapers.base import PortalScraper

_REGISTRY: dict[str, Callable[[], PortalScraper]] = {}


def register(portal: str, factory: Callable[[], PortalScraper]) -> None:
    _REGISTRY[portal] = factory


def get(portal: str) -> PortalScraper | None:
    factory = _REGISTRY.get(portal)
    return factory() if factory is not None else None


def supported() -> list[str]:
    return sorted(_REGISTRY)
