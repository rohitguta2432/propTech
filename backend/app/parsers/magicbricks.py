"""Magicbricks URL parser."""
import re

from app.parsers.base import PortalParser

# Magicbricks listing URLs typically end in `-pdpid-<id>` or contain `/propertyDetails/...`
_PID_RE = re.compile(r"pdpid[-_]([0-9A-Za-z]+)", re.IGNORECASE)
_FALLBACK_RE = re.compile(r"propertyDetails/[^/]+/([0-9A-Za-z\-]+)/?", re.IGNORECASE)


class MagicbricksParser:
    portal = "magicbricks"
    url_regex = re.compile(r"magicbricks\.com/", re.IGNORECASE)

    def extract_listing_id(self, url: str) -> str | None:
        m = _PID_RE.search(url)
        if m:
            return m.group(1)
        m = _FALLBACK_RE.search(url)
        if m:
            return m.group(1)
        # Last-ditch — just hash the path so we have something stable
        return None


_parser: PortalParser = MagicbricksParser()


def parser() -> PortalParser:
    return _parser
