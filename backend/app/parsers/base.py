"""Parser interface — one implementation per portal."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class PortalRoute:
    portal: str
    listing_id: str


class PortalParser(Protocol):
    portal: str
    url_regex: re.Pattern[str]

    def extract_listing_id(self, url: str) -> str | None: ...
