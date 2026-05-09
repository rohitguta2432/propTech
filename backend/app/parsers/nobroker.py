"""NoBroker URL parser."""
import re

from app.parsers.base import PortalParser

_PID_RE = re.compile(r"/property/([a-f0-9]{8,})", re.IGNORECASE)
_FALLBACK_RE = re.compile(r"/([0-9]{6,})/?(?:[?#]|$)")


class NoBrokerParser:
    portal = "nobroker"
    url_regex = re.compile(r"nobroker\.in/", re.IGNORECASE)

    def extract_listing_id(self, url: str) -> str | None:
        m = _PID_RE.search(url)
        if m:
            return m.group(1)
        m = _FALLBACK_RE.search(url)
        return m.group(1) if m else None


_parser: PortalParser = NoBrokerParser()


def parser() -> PortalParser:
    return _parser
