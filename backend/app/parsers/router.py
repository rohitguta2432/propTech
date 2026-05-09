"""Pick the right portal parser by URL."""
import hashlib

from app.parsers import acres99, housing, magicbricks, nobroker
from app.parsers.base import PortalParser, PortalRoute

_PARSERS: list[PortalParser] = [
    magicbricks.parser(),
    acres99.parser(),
    housing.parser(),
    nobroker.parser(),
]


def route(url: str) -> PortalRoute | None:
    """Return (portal, listing_id) for a supported URL, or None.

    If the parser can identify the portal but not extract a listing_id,
    we hash the URL to produce a stable id.
    """
    for parser in _PARSERS:
        if parser.url_regex.search(url):
            listing_id = parser.extract_listing_id(url) or _hash(url)
            return PortalRoute(portal=parser.portal, listing_id=listing_id)
    return None


def _hash(url: str) -> str:
    return "u" + hashlib.sha1(url.encode("utf-8")).hexdigest()[:10]


def supported_portals() -> list[str]:
    return [p.portal for p in _PARSERS]
