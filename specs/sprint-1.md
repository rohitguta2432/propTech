# Sprint 1 — First 14 days

The first concrete development sprint. Goal: a runnable backend with `/v1/check` returning a real (not mock) report for **one Magicbricks Bangalore listing**, end-to-end.

If this works, everything else is repetition.

---

## Sprint goal (definition of done)

By Day 14, you can run:

```bash
curl -X POST http://localhost:8000/v1/check \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.magicbricks.com/propertyDetails/3-BHK-Apartment-FOR-Sale-Whitefield-Bangalore-..."}'
```

…and get a JSON response with a real score, real red flags, computed from a real Magicbricks scrape + real Karnataka RERA lookup.

That's the whole sprint. Everything else (web UI, extension, WhatsApp) is layered on top of this same API in later sprints.

---

## Daily breakdown

### Day 1 — Repo + scaffolding
- [x] Backend folder structure (`backend/`, `backend/app/`, `backend/tests/`)
- [x] `pyproject.toml` or `requirements.txt` with: fastapi, uvicorn, pydantic, pydantic-settings, httpx, playwright, sqlalchemy, alembic, redis, structlog
- [x] `app/main.py` with `/healthz` returning `{"status": "ok"}`
- [x] `.env.example`, `.gitignore`, `Dockerfile`
- **Done when**: `uvicorn app.main:app --reload` starts and `curl localhost:8000/healthz` returns 200.

### Day 2 — Postgres + migrations
- [ ] Set up Supabase project (free tier).
- [ ] Install Alembic, write first migration creating all 7 tables from `database.md`.
- [ ] `app/db/session.py` for SQLAlchemy session.
- [ ] `app/models/db.py` — SQLAlchemy ORM mappings.
- **Done when**: `alembic upgrade head` succeeds against the Supabase DB.

### Day 3 — `/v1/check` skeleton
- [ ] Pydantic request/response schemas matching `api.md`.
- [ ] Route handler that validates URL → returns mock 200 response (hardcoded report).
- [ ] Add structured logging (structlog).
- **Done when**: curl test above returns the mock JSON.

### Day 4 — URL parser + portal detection
- [ ] `app/parsers/base.py` with `BaseParser` protocol.
- [ ] `app/parsers/magicbricks.py` — given URL, extract `listing_id`. Return error for any other domain.
- [ ] `app/parsers/router.py` — pick the right parser by URL.
- [ ] Tests in `tests/test_parsers.py` covering 5 real Magicbricks URLs.
- **Done when**: `/v1/check` correctly identifies portal + listing_id from a real URL.

### Day 5 — Magicbricks HTML scrape
- [ ] Set up Playwright (with `playwright install chromium`).
- [ ] `app/scrapers/magicbricks.py` — fetch + parse: title, price, bhk, area, locality, RERA ID, builder, photos.
- [ ] Cache raw HTML to avoid re-fetching same URL within 24h.
- [ ] Tests with recorded HTML fixtures.
- **Done when**: scraper returns a populated `PropertyContext` for a real URL.

### Day 6 — Karnataka RERA integration
- [ ] `app/integrations/rera_karnataka.py` — given `rera_id`, look it up at `rera.karnataka.gov.in`.
- [ ] Cache results in `rera_records` table for 7 days.
- [ ] Handle: project found / not found / portal unreachable.
- **Done when**: real RERA IDs return real data; fake ones return `MISMATCH`.

### Day 7 — Trust engine v0
- [ ] `app/engine/signals/` with 3 signals only: `RERA_MATCH`, `RERA_MISMATCH`, `LISTING_STALE`.
- [ ] `app/engine/score.py` — aggregator from `trust-engine.md`.
- [ ] Tests covering: clean listing, listing with bad RERA, very old listing.
- **Done when**: `/v1/check` returns a real score using these 3 signals on a real listing.

### Day 8 — Image hash + duplicate detection
- [ ] `app/integrations/image_hash.py` — perceptual hash via `imagehash` Python lib.
- [ ] Insert hashes into `images` table on each scrape.
- [ ] `STOLEN_PHOTOS` signal — query for matching phashes across other properties.
- **Done when**: duplicate-image detection works against test data.

### Day 9 — Locality price benchmark
- [ ] Manually populate `locality_prices` for top 20 Bangalore localities × 3 BHK types from current Magicbricks data (one-time scrape script).
- [ ] `PRICE_BELOW_MARKET` and `PRICE_ABOVE_MARKET` signals.
- **Done when**: a Whitefield 3BHK gets a price-deviation flag.

### Day 10 — Caching layer
- [ ] Upstash Redis setup.
- [ ] Cache `/v1/check` results by URL with 24h TTL.
- [ ] `cache_hit: true` field returned correctly.
- **Done when**: second curl on same URL completes in <500ms.

### Day 11 — Rate limiting
- [ ] `slowapi` integration.
- [ ] 10 checks/min/IP for free tier.
- [ ] `429` response with proper headers.
- **Done when**: 11th request in 60s returns 429.

### Day 12 — Feedback endpoint
- [ ] `POST /v1/feedback` writes to `feedback` table.
- [ ] Email notification (Resend) to founder on each new flag.
- **Done when**: a feedback POST creates a row + sends an email.

### Day 13 — Deploy to Railway
- [ ] Railway project, link to GitHub.
- [ ] Env vars set (DB url, Redis url, secrets).
- [ ] Auto-deploy on push to `main`.
- [ ] Custom domain `api.propcheck.in`.
- **Done when**: `curl https://api.propcheck.in/healthz` returns 200.

### Day 14 — End-to-end manual test
- [ ] Hand-pick 10 real Magicbricks Bangalore listings (mix of clean + suspicious).
- [ ] Run `/v1/check` against each on production.
- [ ] Verify scores feel right against your own intuition.
- [ ] Document calibration results in `specs/calibration-day14.md`.
- **Done when**: 8/10 listings have a score that matches your manual judgment.

---

## What we're NOT building in Sprint 1

- No web UI. No Chrome extension. No WhatsApp bot.
- No 99acres / Housing / NoBroker parsers.
- No image reverse search via Google Vision (stretch goal in Sprint 2).
- No B2B API key auth.
- No payments.
- No marketing site.

These come in Sprint 2 onwards.

---

## Risks for this sprint

| Risk | Mitigation |
|---|---|
| Magicbricks blocks our scrapes | Use Playwright with realistic browser fingerprint. Rate-limit our own fetches. Don't crawl in bulk. |
| Karnataka RERA portal is flaky | Cache aggressively (7-day TTL). Graceful degradation when portal down. |
| Schema design mistakes surface only at integration | Run end-to-end tests on Day 7 onwards. |
| Founder is not full-time technical | Pair with Claude Code or Cursor. Each daily task is small enough to AI-pair through. |

---

## Sprint review (Day 14)

Honest answer to three questions:

1. **Does the API actually work?** Yes / no / mostly.
2. **How accurate is the score on real listings?** (calibration metric — see `trust-engine.md`)
3. **What did I underestimate?** Note for Sprint 2 planning.
