"""99acres URL parser."""
import re

from app.parsers.base import PortalParser

_PID_RE = re.compile(r"-(spid|pid)-([A-Z0-9]+)", re.IGNORECASE)


class NinetyNineAcresParser:
    portal = "99acres"
    url_regex = re.compile(r"99acres\.com/", re.IGNORECASE)

    def extract_listing_id(self, url: str) -> str | None:
        m = _PID_RE.search(url)
        return m.group(2) if m else None


_parser: PortalParser = NinetyNineAcresParser()


def parser() -> PortalParser:
    return _parser
