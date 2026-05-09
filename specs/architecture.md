# Architecture

System design for the property listing trust layer. One backend, three surfaces.

---

## High-level diagram

```
                    ┌─────────────────────────────────────────────┐
                    │              Three Surfaces                 │
                    │                                             │
   ┌────────────┐   │   ┌──────────┐  ┌──────────┐  ┌──────────┐  │
   │   USER     │──▶│   │   Web    │  │  Chrome  │  │ WhatsApp │  │
   │            │   │   │ Next.js  │  │Extension │  │  (Twilio)│  │
   └────────────┘   │   └────┬─────┘  └────┬─────┘  └────┬─────┘  │
                    └────────┼─────────────┼─────────────┼─────────┘
                             │             │             │
                             └─────────────┼─────────────┘
                                           │
                                           ▼
                    ┌──────────────────────────────────────────┐
                    │         Backend API (FastAPI)             │
                    │  /v1/check  /v1/portals  /v1/feedback     │
                    └─────────┬────────────────┬────────────────┘
                              │                │
                ┌─────────────┘                └──────────────┐
                ▼                                             ▼
       ┌────────────────┐                         ┌────────────────────┐
       │  Trust Engine  │                         │  Async Workers     │
       │  (rules v1)    │                         │  (Playwright,      │
       │                │                         │   image hash,      │
       │  Aggregates    │                         │   RERA fetch)      │
       │  8 signals →   │                         │                    │
       │  score 0-100   │                         └─────────┬──────────┘
       └───────┬────────┘                                   │
               │                                            │
               └─────────────┬──────────────────────────────┘
                             ▼
              ┌──────────────────────────────────┐
              │            Data Layer            │
              │                                  │
              │  Postgres (Supabase) — structured│
              │  Redis (Upstash) — 24h cache     │
              │  R2 (Cloudflare) — screenshots   │
              └──────────────────────────────────┘
                             │
                             ▼
            ┌────────────────────────────────────┐
            │         External integrations      │
            │                                    │
            │  • Karnataka RERA portal           │
            │  • Google Vision (reverse images)  │
            │  • Property tax records (BMRDA)    │
            │  • Twilio WhatsApp Business API    │
            │  • Bright Data proxies (on demand) │
            └────────────────────────────────────┘
```

---

## What happens during a single check

1. User submits a Magicbricks/99acres/Housing/NoBroker URL on any of the 3 surfaces.
2. API receives the URL → identifies portal + property ID → checks Redis cache.
3. **Cache hit (under 24h old)** → return cached report instantly.
4. **Cache miss** → fan out 6 parallel jobs:
   - Scrape listing HTML via Playwright + rotating proxy
   - Hash listing photos + reverse-search via Google Vision
   - Look up locality price benchmark
   - Cross-check builder + project against Karnataka RERA
   - Compare against existing properties DB for duplicates
   - Pull builder complaint count
5. Trust engine aggregates all 6 signals, applies rules v1, produces:
   - Score 0–100
   - Red flag list (with reasons + sources)
   - Green flag list
   - Pre-purchase checklist
6. Save to Postgres + Redis. Return to user. Total time: <5s on cache miss, <500ms on cache hit.

---

## Components

### Frontend

| Surface | Stack | Path | Hosting |
|---|---|---|---|
| Web | Next.js 14 + Tailwind + shadcn/ui | `web/` | Vercel |
| Chrome extension | TypeScript + Manifest V3 | `extension/` | Chrome Web Store |
| WhatsApp | (server-side webhook handler — no separate frontend) | `api/whatsapp/` | Twilio routes to backend |

### Backend

| Module | Purpose |
|---|---|
| `api/` | FastAPI HTTP server. Endpoints: `/v1/check`, `/v1/check/{id}`, `/v1/portals`, `/v1/feedback`, `/v1/whatsapp/webhook` |
| `workers/` | Async job runners (RQ on Redis). Heavy lifting: scraping, image search, RERA fetch |
| `engine/` | Trust scoring rules. v1 = pure Python rules, no ML in scoring (the LLM only runs in the parsing layer below). |
| `parsers/` | Per-portal URL parsers (regex). One file per portal. Easy to add new ones |
| `scrapers/` | Per-portal HTML scrapers (regex/BS4-first). LLM fallback fires only when regex leaves key fields blank. |
| `integrations/` | Wrappers for RERA, locality prices, image hash, **LLM parsing fallback (Gemma 4 31B via OpenRouter)**, Twilio |

### Data

**Postgres tables (Supabase):**

| Table | Holds |
|---|---|
| `checks` | Every user-submitted check: URL, portal, score, flags JSON, timestamps |
| `properties` | Normalized listing snapshots — used for duplicate detection |
| `portals` | Portal metadata + parser version |
| `images` | Perceptual hash + URL for every listing photo we've seen |
| `locality_prices` | Avg ₹/sqft per locality per BHK type, refreshed monthly |
| `rera_records` | Cached RERA project data (state, project ID, complaints) |
| `builder_complaints` | Builder name → complaint count + delay history |
| `feedback` | User-flagged wrong scores → manual review queue |

**Redis (Upstash):**
- Per-URL hot cache, 24h TTL
- Rate limit counters (per IP)

**Cloudflare R2:**
- Full-page screenshots when needed for fraud evidence

### External APIs

| Service | Why | Cost (est.) |
|---|---|---|
| **OpenRouter (Gemma 4 31B free tier)** | **LLM parsing fallback when scraper regex leaves key fields blank** | **Free ($0/M tokens) — gated on `OPENROUTER_API_KEY` env var; no-op when unset** |
| Karnataka RERA portal | Project verification | Free (web scrape) |
| Google Vision API | Reverse image search | $1.50 / 1K queries |
| Twilio WhatsApp Business | Bot transport | $0.005 / message |
| Bright Data residential proxies | Listing scrape | $500/month entry tier |
| BMRDA / property tax sites | Owner-name match | Free (web scrape) |

---

## Stack — choices and why

| Choice | Why |
|---|---|
| **FastAPI** | Async-native, fast, great for I/O-heavy jobs. Pydantic validation built in |
| **Postgres on Supabase** | Generous free tier, easy auth later, row-level security if we go multi-tenant |
| **Redis on Upstash** | Pay-per-request, fits spiky workloads, no server to manage |
| **Vercel for web** | Free, fast, zero-config with Next.js |
| **Railway for backend** | Cheap (~₹2K/month), Python-friendly, simple deploys |
| **Playwright (not requests/BS4)** | Many portals are JS-rendered. Playwright handles both static + dynamic |
| **shadcn/ui** | Copy-paste components, full control, no runtime dependency, looks good |
| **Manifest V3** | Required by Chrome from 2024+. Service worker model |
| **RQ over Celery** | Simpler, Redis-only, fewer moving parts at our scale |

---

## API contract (v1)

### `POST /v1/check`
Request:
```json
{ "url": "https://www.magicbricks.com/propertyDetails/3-BHK-..." }
```
Response (200):
```json
{
  "id": "chk_abc123",
  "score": 42,
  "label": "risky",
  "summary": "This listing has 4 high-risk signals.",
  "property": {
    "portal": "magicbricks",
    "title": "3 BHK in Whitefield",
    "price_inr": 12000000,
    "bhk": 3,
    "area_sqft": 1450,
    "locality": "Whitefield",
    "city": "Bangalore"
  },
  "red_flags": [
    {
      "code": "DUPLICATE_LISTING",
      "label": "Listed 4 times across 3 portals at different prices",
      "evidence": ["url1", "url2", "url3", "url4"],
      "severity": "high"
    }
  ],
  "green_flags": [],
  "checklist": [
    "Visit the property in person before paying any token",
    "Ask for the sale deed and verify property tax record",
    "Never pay token over UPI to a personal account"
  ],
  "verifications": {
    "rera": { "status": "MISMATCH", "expected": "PRM/KA/RERA/...", "found": null },
    "image_match_count": 7,
    "locality_avg_price_per_sqft": 8500,
    "listing_age_days": 87
  },
  "checked_at": "2026-05-09T11:30:00Z",
  "cache_hit": false
}
```

### `GET /v1/check/{id}` — fetch a previous report
### `POST /v1/feedback` — user reports a wrong score
### `POST /v1/whatsapp/webhook` — Twilio inbound webhook

---

## Deployment topology

```
GitHub (main branch)
   │
   ├─▶ Vercel ──── propcheck.in (web + landing)
   │
   └─▶ Railway ─── api.propcheck.in (FastAPI + workers)
                        │
                        ├─▶ Supabase (Postgres)
                        ├─▶ Upstash (Redis)
                        ├─▶ Cloudflare R2 (screenshots)
                        └─▶ External APIs
```

Cloudflare in front of everything for DDoS, rate limit, caching static assets.

---

## Security

- Rate limit: **10 checks/IP/min** (free), **120/min** for Pro keys.
- No auth at MVP for free checks. Cookie-based usage tracking only.
- API key auth for Pro tier + B2B (header: `X-API-Key`).
- Input validation: URL must match a known portal regex. Reject everything else.
- Output: never echo user-supplied URL into HTML without escaping.
- Secrets: Railway environment vars only, never in repo.
- HTTPS only. HSTS preload.
- Logging: never log full URLs with query strings (may contain owner names).

---

## Scaling plan

| Stage | MAU | Action |
|---|---|---|
| 0–10K | Single Railway box, Supabase free tier | Stay simple |
| 10K–50K | Add 2nd worker, upgrade Supabase | Move proxy provider to higher tier |
| 50K–200K | Split API and workers, add CDN for static reports | Postgres read replica |
| 200K+ | Multi-region, queue-based architecture, possibly move to AWS | Hire infra engineer |

---

## Observability

| Layer | Tool | Why |
|---|---|---|
| Errors | Sentry | Free tier covers MVP |
| Logs | Axiom or Logtail | Cheap, query-friendly |
| Product analytics | PostHog | Free self-hosted option, funnel + sessions |
| Web analytics | Plausible | GDPR-clean, lightweight |
| Uptime | Better Stack | Free for MVP |

---

## Cost (first 90 days)

| Item | ₹ / month |
|---|---|
| Vercel | 0 (free tier) |
| Railway | ~2,000 |
| Supabase | 0 → 2,000 |
| Upstash Redis | ~500 |
| Cloudflare | 0 (free) + R2 ~500 |
| Twilio sandbox | 0 |
| Google Vision (1K checks/day) | ~3,000 |
| Bright Data proxies | ~40,000 |
| Sentry / Plausible / etc | ~1,000 |
| **Total / month** | **~₹47,000** |

Domain + SaaS one-time: ~₹10K. **Total 90-day infra: ~₹1.5L.** Reduce proxy spend by starting with free public proxies + scaling only when scrapes get blocked.

---

## What we're NOT building at MVP

- No mobile app — web works fine on phone
- No user accounts — stateless free tier
- No payments — wait until Pro launch in Month 4
- **No ML in the scoring engine** — rules engine is more explainable + debuggable (the LLM-based parsing fallback in `app/integrations/llm_parser.py` is a separate concern: it only fills gaps when regex parsers can't extract a field; scoring stays rules-based and auditable)
- No multi-language UI — English only at launch
- No commercial / land / plot support — residential only
- No portal-specific dashboards — just the score
