# Scrapers Spec

How each portal scraper extracts a normalized listing from a URL. Shared interface so the trust engine consumes one shape, regardless of source.

---

## Constraints

- **No Playwright at MVP.** We're on Vercel Python serverless (10s execution limit, no headful Chromium). Use `httpx` (async) + `BeautifulSoup4`.
- If a portal is JS-rendered and httpx returns thin HTML, the scraper returns what it has and the trust engine downgrades the score with a `INSUFFICIENT_DATA` low-confidence flag — never crashes the request.
- All scrapers are **on-demand only** (called from `/v1/check`). No bulk crawling.
- Send a realistic `User-Agent` and `Accept-Language` so we don't get insta-blocked.
- Honour 5s timeout; if exceeded, return a `ScrapedListing` with whatever's set + log the timeout.

### LLM parsing fallback (regex-first, LLM-only-when-gaps)

After the per-portal regex/BS4 parser runs, scrapers call
`app.integrations.llm_parser.enrich(html, listing)` which is a no-op unless:

1. `OPENROUTER_API_KEY` is set in the environment, AND
2. At least 2 of `{price_inr, area_sqft, bhk, locality}` are still `None` after regex.

When both conditions hold, the raw HTML (truncated to 12K chars) is sent to
**Gemma 4 31B via OpenRouter free tier** with a strict-JSON prompt. The
returned fields **only fill gaps** — regex always wins on overlap. Failures
(network, timeout, malformed JSON, refusal) silently return the regex-only
listing. The LLM never participates in scoring (see `specs/integrations.md`
section 4 for the full contract).

This keeps two principles intact:
- **Scoring stays rules-based and auditable** (`specs/trust-engine.md`).
- **Parsing degrades gracefully**: regex-only is the floor, LLM is upside.

---

## Common interface

```python
# backend/app/scrapers/base.py
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol


@dataclass
class ScrapedListing:
    portal: str
    listing_id: str
    url: str

    # All fields below are best-effort; None means "couldn't extract".
    title: str | None = None
    price_inr: int | None = None
    bhk: int | None = None
    area_sqft: int | None = None
    locality: str | None = None
    city: str | None = None
    state: str | None = None
    rera_id: str | None = None
    builder_name: str | None = None
    listed_at: datetime | None = None
    image_urls: list[str] = field(default_factory=list)
    description: str | None = None
    raw_html_snippet: str | None = None      # first 4kb of body for debugging
    fetch_error: str | None = None           # set when fetch fails


class PortalScraper(Protocol):
    portal: str

    async def fetch(self, url: str, listing_id: str) -> ScrapedListing: ...
```

Each portal scraper lives at `backend/app/scrapers/<portal>.py` and exports `parser()` returning a `PortalScraper` instance.

---

## What to extract per portal

| Field | Source signal | Fallback |
|---|---|---|
| `title` | `<h1>` near top of page, or `og:title` meta | None |
| `price_inr` | regex `(\d[\d,]*\s*(?:Cr|Lac|Lakh|L|K))` and convert to integer rupees | None |
| `bhk` | regex `(\d+)\s*BHK` | None |
| `area_sqft` | regex `(\d+(?:\.\d+)?)\s*(?:sq\.?\s?ft|sqft|sq ft)`, also accept "Carpet Area:" labels | None |
| `locality`, `city` | breadcrumbs, og:title, address blocks | None |
| `rera_id` | regex `(?:RERA(?:\s*ID)?\s*[:\-]?\s*)([A-Z0-9/\-]{10,})` | None |
| `builder_name` | "By:" / "Builder:" labels, project metadata | None |
| `listed_at` | "Posted on" / "Updated on" date strings | None |
| `image_urls` | `<img>` tags with property-photo class names; up to 12 unique | `[]` |
| `description` | first 1500 chars of any `<div class="description">` / `og:description` | None |

---

## Tests

Each scraper ships with a fixture-based test:

```
backend/tests/fixtures/<portal>/
  ├── sample-1.html        (raw HTML captured from a real listing)
  └── expected-1.json      (the expected ScrapedListing fields)
```

A pytest test loads the fixture, calls the parser (without network), asserts the parsed shape matches.

The fixture HTML files are committed (small, no PII), expected JSON is committed.

---

## Deliverables per portal

Each agent produces:

1. `backend/app/scrapers/<portal>.py` — implementing `PortalScraper`.
2. `backend/tests/fixtures/<portal>/sample-1.html` — a small representative HTML snippet (it can be a stub if a real fetch isn't possible).
3. `backend/tests/fixtures/<portal>/expected-1.json` — expected parsed values.
4. `backend/tests/test_<portal>_scraper.py` — pytest tests.

All scrapers must:
- Be `async` and use `httpx.AsyncClient` for fetch.
- Tolerate every field being missing without raising.
- Set `fetch_error` on network failure rather than throwing.
- Return a `ScrapedListing` even if everything is None except `portal`/`listing_id`/`url`.

---

## Out of scope at MVP

- JavaScript rendering. If a portal needs JS, scraper returns minimal data + we accept the gap. Migrate to Playwright on Railway later.
- Image downloading. We only collect URLs; image hashing happens in a separate module that may run async.
- Anti-bot evasion (proxies, fingerprinting). Add when portals start blocking.
