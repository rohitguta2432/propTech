"""Deterministic slug helpers.

Builder profile pages (`/builder/<slug>`) need a stable mapping between a
free-text builder name as it appears on a portal ("Prestige Estates Projects
Ltd.", "PRESTIGE ESTATES", "Prestige  Estates  Projects") and a single URL
slug. We normalize aggressively so all three of those resolve to the same
public page and so the SEO surface doesn't fragment across casing or
punctuation noise.
"""
from __future__ import annotations

import re
import unicodedata

# Corporate / sectoral suffixes we strip after slugification. Indian
# developers are routinely listed with these in some portals and bare in
# others; dropping them collapses the obvious duplicates.
_SUFFIX_TOKENS = (
    "private-limited",
    "pvt-ltd",
    "pvt-limited",
    "limited",
    "ltd",
    "llp",
    "inc",
    "corporation",
    "corp",
    "company",
    "co",
    "group",
    "developers",
    "developer",
    "builders",
    "builder",
    "constructions",
    "construction",
    "infrastructure",
    "infra",
    "projects",
    "estates",
    "realty",
    "realtors",
    "properties",
    "homes",
)


def to_slug(name: str | None) -> str | None:
    """Normalize a free-text builder name to a stable URL slug.

    Returns None for empty / unusable input so callers can short-circuit
    without first-class None checks. Strips ASCII accents, lowercases,
    collapses any run of non-alphanumerics to a single hyphen, then
    repeatedly trims well-known corporate suffix tokens off the tail.
    """
    if not name:
        return None
    s = unicodedata.normalize("NFKD", name)
    s = s.encode("ascii", "ignore").decode("ascii")
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    if not s:
        return None
    # Repeatedly strip trailing suffix tokens. "foo-developers-pvt-ltd" →
    # "foo-developers-pvt" → "foo-developers" → "foo".
    changed = True
    while changed:
        changed = False
        for suf in _SUFFIX_TOKENS:
            if s.endswith("-" + suf):
                s = s[: -(len(suf) + 1)]
                changed = True
                break
            if s == suf:
                return None
    return s or None
