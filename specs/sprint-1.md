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

### Day 2 — Postgres + migrations ✅
- [x] **Supabase Postgres provisioned** — project `propcheck` in `rohitguta2432's Org`, region Asia-Pacific (Singapore, ap-southeast-1).
- [x] Install Alembic + SQLAlchemy + psycopg2-binary.
- [x] First migration creating all 7 tables — `migrations/versions/2026_05_09_0001_initial_schema.py`.
- [x] `app/db/session.py` for SQLAlchemy engine + session factory (lazy).
- [x] `app/db/base.py` declarative Base.
- [x] `app/models/db.py` — SQLAlchemy ORM mappings (all 7 tables).
- [x] **`alembic upgrade head` succeeded against Supabase**. 8 tables exist (7 app + alembic_version).
- [x] Using Supabase **Session Pooler** at `aws-1-ap-southeast-1.pooler.supabase.com:5432` — IPv4-friendly, supports prepared statements (so Alembic just works), DNS resolves on JioFiber. **No PGHOSTADDR workaround needed.**
- **Connection string** (in `backend/.env`, not committed): `postgresql://postgres.<project_ref>:<password>@aws-1-ap-southeast-1.pooler.supabase.com:5432/postgres`
- **History note**: We initially provisioned Vercel Postgres (Neon) but JioFiber router DNS couldn't resolve `*.neon.tech`, so we switched to Supabase. Vercel Postgres has been deleted.
- **Verified**: `alembic current` returns `0001_initial_schema (head)`.

### Day 3 — `/v1/check` skeleton
- [ ] Pydantic request/response schemas matching `api.md`.
- [ ] Route handler that validates URL → returns mock 200 response (hardcoded report).
- [ ] Add structured logging (structlog).
- **Done when**: curl test above returns the mock JSON.

### Day 4 — URL parser + portal detection ✅
- [x] `app/parsers/base.py` with `PortalParser` protocol.
- [x] **All 4 portals** parsed (not just Magicbricks): `magicbricks.py`, `acres99.py`, `housing.py`, `nobroker.py`.
- [x] `app/parsers/router.py` — picks the right parser by URL regex; falls back to URL hash if listing_id can't be extracted.
- [x] `/v1/check` integrates the router — invalid URLs now return `INVALID_URL` 400 with the list of supported portals.
- [x] Cache lookup added: same URL within 24h returns the cached row from Postgres (`cache_hit: true`).
- [x] Persistence: every check writes to the `checks` table with the parsed portal, listing_id, IP, user-agent, and source surface.
- **Verified**: tested all 4 portals locally; cache hits on repeat calls. Live in production at `api.rohitraj.tech/v1/check`.

### Day 5 — Magicbricks HTML scrape ✅ (and 99acres + scrapers spec)
- [x] **No Playwright** at MVP (Vercel 10s ceiling) — using `httpx` + `BeautifulSoup4` with 6s timeout.
- [x] `specs/scrapers.md` written — common `ScrapedListing` shape, `PortalScraper` protocol.
- [x] `app/scrapers/{base,router}.py` — registry, defaults (User-Agent, timeout).
- [x] `app/scrapers/magicbricks.py` — fixture-tested (6/6 pass), registers itself with router.
- [x] `app/scrapers/acres99.py` — fixture-tested (9/9 pass), registers itself with router.
- [x] 24h DB cache wired through `/v1/check` (re-uses Day 4 work).
- **Limitation**: Vercel egress IPs are likely blocked by portal anti-bot. When that happens, scrapers return empty `ScrapedListing` → `/v1/check` falls back to the stub. Migrate to Railway + residential proxies later.

### Day 6 — Karnataka RERA integration ✅
- [x] `specs/integrations.md` written.
- [x] `app/integrations/rera_karnataka.py`: `lookup(rera_id, db)` returns `RERAResult` with status MATCH | MISMATCH | NOT_FOUND | NOT_PROVIDED | PORTAL_UNREACHABLE.
- [x] 7-day cache on `rera_records` table — first hit fetches, subsequent return from DB.
- [x] Lossy parser: matches even when portal HTML structure is unrecognisable (so we don't fail on layout changes).
- [x] 9/9 tests pass (cache hit, miss, 404, 5xx, unreachable, lossy parse).
- **Note**: live endpoint URL guess `rera.karnataka.gov.in/projectViewDetails?projectId=...` — verify with one real id before relying on it.

### Day 7 — Trust engine v0 ✅
- [x] `app/engine/trust_score.py` rewritten with real signal logic.
- [x] Implemented: `RERA_MATCH` (+10), `RERA_MISMATCH` (-25), `RERA_MISSING` (-10 if area>=800sqft), `PRICE_BELOW_MARKET` (-10 if <-15%), `PRICE_ABOVE_MARKET` (-5 if >+25%), `LISTING_STALE` (-5 if >180d).
- [x] Aggregation: 100 base, clamp [0..100], bands at 70 (safe) / 40 (caution).
- [x] `_is_empty()` fallback: if scraper returned literally nothing, `/v1/check` falls back to `compute_stub` so the UI never breaks.
- [x] Local smoke test: Whitefield 3BHK example produces `score=80, label=safe` with PRICE_BELOW_MARKET (-26%) + RERA_MISSING flags. Pulls real avg ₹11,200/sqft from the seeded `locality_prices` table.

### Day 8 — Image hash + duplicate detection
- [ ] `app/integrations/image_hash.py` — perceptual hash via `imagehash` Python lib.
- [ ] Insert hashes into `images` table on each scrape.
- [ ] `STOLEN_PHOTOS` signal — query for matching phashes across other properties.
- **Done when**: duplicate-image detection works against test data.

### Day 9 — Locality price benchmark ✅
- [x] Curated CSV seed (instead of scrape) at `backend/seeds/locality_prices_bangalore.csv` — 20 Bangalore localities × {1,2,3,4} BHK = 80 rows.
- [x] `app/integrations/locality_prices.py`: `get_avg_price(city, locality, bhk, db)` (case-insensitive) and `load_seed(csv, db)` with Postgres `ON CONFLICT (city,locality,bhk) DO UPDATE` upsert.
- [x] `scripts/seed_locality_prices.py` — runnable; ran successfully against live Supabase, confirmed 80 rows persisted.
- [x] `PRICE_BELOW_MARKET` and `PRICE_ABOVE_MARKET` signals wired in trust engine — see Day 7.
- [x] 4/4 tests pass.

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

### Day 13 — Deploy ✅ (changed: Vercel Python serverless instead of Railway)
- [x] **Backend deployed to Vercel** as `propcheck-api` (Python @vercel/python runtime, ASGI app).
- [x] Env vars set: `DATABASE_URL` for production, preview, development.
- [x] Auto-deploy on push to `main` (Vercel git integration).
- [x] **Custom domain `api.rohitraj.tech`** attached.
- [x] **Frontend deployed to Vercel** as `propcheck-app` (Next.js 14 + Tailwind, all design tokens from mockup applied).
- [x] **Custom domain `propcheck.rohitraj.tech`** attached.
- [x] `NEXT_PUBLIC_API_BASE=https://api.rohitraj.tech` baked into the frontend build.
- **Why not Railway**: User had Vercel set up already; Vercel Python serverless ships fine for the MVP (mock scoring). When Day 5+ adds Playwright scraping with multi-second runs, we'll move backend to Railway/Fly.
- **Verified**:
  - `curl https://api.rohitraj.tech/healthz` → 200
  - `curl -X POST https://api.rohitraj.tech/v1/check ...` → full report, persisted to Supabase
  - `curl https://propcheck.rohitraj.tech` → 200, served Next.js app
  - Page bundle embeds `api.rohitraj.tech` as the API base.

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
