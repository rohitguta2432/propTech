"""Housing.com URL parser."""
import re

from app.parsers.base import PortalParser

_PID_RE = re.compile(r"/(rd|ds)/([0-9a-zA-Z]+)(?:[/?#]|$)")


class HousingParser:
    portal = "housing"
    url_regex = re.compile(r"housing\.com/", re.IGNORECASE)

    def extract_listing_id(self, url: str) -> str | None:
        m = _PID_RE.search(url)
        return m.group(2) if m else None


_parser: PortalParser = HousingParser()


def parser() -> PortalParser:
    return _parser
