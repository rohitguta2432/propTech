# PROJECT — PropCheck

> Property listing trust layer for India. Free for buyers; B2B API for banks doing home-loan diligence.

## Vision

Every Indian property buyer faces the same trust gap: a listing too good to be true, a broker pressing for a quick token, a RERA number that doesn't add up, photos lifted from elsewhere. ₹10K–₹2L lost per scam, almost always before any lawyer or bank gets involved. The portals can't fix this — they earn from every listing, real or fake.

PropCheck is the neutral check that should have been there all along.

## Audience

- **Primary (free)** — buyers and renters on Magicbricks, 99acres, Housing.com, NoBroker.
- **Primary (paid)** — banks and NBFCs running property due-diligence as part of home-loan disbursement.
- **Secondary** — NRIs buying remotely, investors with multi-property tracking, journalists.

## Core promise

Paste any portal listing URL → 0–100 Trust Score in 30 seconds → explainable red flags + pre-purchase checklist + cited sources.

## Locked decisions

> Anything below is fixed unless explicitly re-decided. Treat these as ADRs.

- **Backend**: FastAPI (Python 3.11) on Vercel @vercel/python. Will migrate to Railway when scraping needs >10s.
- **Frontend**: Next.js 14 (App Router) on Vercel.
- **Database**: Supabase Postgres (ap-southeast-1, Session pooler — IPv4-friendly + supports prepared statements).
- **LLM parsing fallback**: Gemma 4 31B via OpenRouter free tier ($0/M tokens). Regex-first, LLM-only-when-gaps. Gated on `OPENROUTER_API_KEY` env var (no-op when unset). The LLM **never participates in scoring** — it only fills gaps in the upstream parsing layer. See `specs/integrations.md` § 4.
- **Auth**: None at MVP. API keys (`pk_*` / `bk_*`) for Pro/B2B come later.
- **Domains**: `propcheck.rohitraj.tech` (web), `api.rohitraj.tech` (api). Move to a real domain after brand lock.
- **Design system**: Anthropic hybrid — Poppins headings, Lora body, JetBrains Mono for data, Anthropic Orange for CTAs, traffic-light functional palette for safety scores.
- **Tests-required**: every new feature ships with pytest tests; CI runs them on push to main + PRs.
- **No PII**: at MVP we never ask for name, phone, Aadhaar, payments. Stored data is URLs + IPs + UA only.
- **Rate limit**: 10 req/min/IP anonymous; pro/B2B keys bypass via cost_func=0.

## Open decisions

- Final brand name (PropCheck is working) and registered domain.
- Funding model (bootstrap vs pre-seed angel).
- Team model (solo + AI / hire dev / co-founder).
- Real-scrape strategy (Railway migration vs proxy provider vs Firecrawl).

## Success criteria (Sprint 1 milestone)

- ✅ Live frontend + backend on custom domains.
- ✅ DB persistence + 24h cache.
- ✅ All 4 portal URL parsers + Magicbricks/99acres scrapers.
- ✅ Karnataka + Maharashtra RERA dispatcher.
- ✅ Trust engine v1 with 6 wired signals.
- ✅ Locality price index for 7 Indian cities (~400 rows).
- ✅ Rate limiting + feedback endpoint.
- ✅ Privacy/Terms/About/404/sitemap/robots.
- ⏳ Real-listing calibration (Day 14) — needs real URLs.
- ⏳ Real-scrape working from production (blocked on hosting migration).
