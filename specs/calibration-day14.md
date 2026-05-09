# Calibration — Sprint 1 Day 14

> Generated 2026-05-09 by `backend/scripts/calibrate.py`. Re-run any time deltas change.

## Method

Couldn't reach real Magicbricks/99acres/Housing/NoBroker URLs from this IP — every portal returned 403/404/406 to `httpx`, and Wayback Machine has no recent snapshots of those domains either. So calibration ran against:

1. The real-shaped HTML fixtures we already have (`tests/fixtures/{magicbricks,99acres}/sample-1.html`).
2. Five synthetic listings crafted to exercise specific signal combinations.

For each, we ran the full pipeline: regex parser → LLM gap-fill (Gemma 4 31B via OpenRouter) → trust engine.

## Results

| Listing | Score | Band | Flags fired |
|---|---:|---|---|
| Magicbricks fixture (Whitefield 3BHK ₹1.2Cr) | 90 | safe | PRICE_BELOW_MARKET (medium) |
| 99acres fixture (Indiranagar 2BHK ₹1.85Cr) | 100 | safe | — |
| Synthetic clean (Whitefield 3BHK fair price + RERA + fresh) | 100 | safe | — |
| Synthetic below-market (30% under) | 90 | safe | PRICE_BELOW_MARKET |
| Synthetic no-RERA (1450sqft, no RERA ID) | 90 | safe | RERA_MISSING |
| Synthetic stale (240 days old) | 95 | safe | LISTING_STALE |
| **Synthetic scammy (48% under + no RERA + 300d old)** | **75** | **safe** | RERA_MISSING + PRICE_BELOW_MARKET + LISTING_STALE |

## Findings

### ✅ Working correctly
- Each signal fires when its trigger condition is met.
- Each signal's delta lands at the spec'd value (no off-by-one).
- The locality price index resolves correctly for both Bangalore localities tested.
- Regex parser already extracted everything in both fixtures — LLM didn't need to fire (correct regex-first behaviour).
- RERA verification correctly returns `PORTAL_UNREACHABLE` when Karnataka portal returns a non-200 (we get 405 from `https://rera.karnataka.gov.in/projectViewDetails?projectId=...` — the URL pattern guess is wrong; needs verification with a real ID).

### ⚠️ Critical calibration issue: deltas too soft

**A listing with three stacked red flags scores 75 (safe).**

A flat that's 48% below market + has no RERA + is 300 days old should *clearly* be at least "caution" (40–69), arguably "risky" (<40). Today's spec produces 100 − 10 − 10 − 5 = 75.

This is a known-bad result. The product promise is *"explainable trust score that buyers can act on"* — a 75/safe on a clearly-suspicious listing fails that promise.

### Recommended delta updates

Update `specs/trust-engine.md`:

| Signal | Current Δ | Proposed Δ | Why |
|---|---:|---:|---|
| `RERA_MISSING` | −10 | **−15** | Big flat with no RERA ID is closer to a fraud signal than a soft heuristic. |
| `PRICE_BELOW_MARKET` (≥15%) | −10 | **−15** | Sub-15% is the "risky" band that drives most actual fraud. |
| `PRICE_BELOW_MARKET` (≥30%) | — | **−25** (escalated) | Add a tier — 30%+ below is almost always a scam. |
| `LISTING_STALE` (>180d) | −5 | **−10** | Listings active 6+ months are typically problematic. |
| `LISTING_STALE` (>365d) | — | **−15** (escalated) | Add a tier. |
| **NEW: `MULTIPLE_FLAGS` multiplier** | — | **−10** for any 3+ red flags | Stacking multiplier — three independent issues compound. |

Re-running with these deltas, the synthetic scammy listing would score:
100 − 25 (≥30% under) − 15 (RERA missing) − 15 (>365d stale) − 10 (3+ flags) = **35 → risky** ✓

The clean fixtures should still score 90+ because they trigger 0–1 signals.

### Open question: RERA endpoint URL

Karnataka RERA returns 405 to `https://rera.karnataka.gov.in/projectViewDetails?projectId=PRM/KA/...`. Our endpoint guess is wrong. Action: capture a real Karnataka RERA project lookup from a browser (Network tab → look at the actual XHR / form POST endpoint), then update `app/integrations/rera_karnataka.py`. Until then, every listing scores RERA as `PORTAL_UNREACHABLE` (silent — no flag), so we're missing positive RERA_OK and negative RERA_MISMATCH outcomes.

## Real-URL run (2026-05-09 attempt)

Pulled 7 real listing URLs from web search (3 from 99acres, 4 from NoBroker — Magicbricks/Housing didn't index detail pages with discoverable URLs). Findings:

| Portal | Local fetch | Notes |
|---|---|---|
| Magicbricks | n/a — no real URLs found via Google | Detail pages don't get indexed easily |
| 99acres | **HTTP 403** on every detail URL | Aggressive anti-bot from this IP |
| Housing.com | **HTTP 406** on root | Also blocked |
| NoBroker | **HTTP 200 with full 270–360KB HTML** | The only one we could fetch |

So NoBroker is the only portal we can fetch from a residential IP. But:

- NoBroker is a **Next.js SPA** — listing data isn't in the body HTML, it's in `<script id="__NEXT_DATA__">…</script>` as embedded JSON.
- We updated `llm_parser._trim_html` to harvest hydration scripts (`__NEXT_DATA__` + `application/ld+json`) and prioritise them over visual HTML in the LLM prompt. Truncation budget bumped 12K→30K to fit hydration payloads.
- **OpenRouter free Gemma 4 31B is intermittently rate-limited** — about half our calls today returned "Provider returned error" (upstream Google AI Studio throttle). Successful calls correctly extract structured data; failed calls leave the listing empty (graceful degradation).

Net result: every real-URL run today either fetched-then-failed-LLM (NoBroker) or failed-fetch-outright (99acres / Housing / Magicbricks).

### Real options to actually unblock real-URL calibration

1. **Load $10 credits on OpenRouter** — one-time, becomes spendable credit, unlocks ~10× free-tier rate limits per their public docs. Single biggest unblock.
2. **Pivot to Groq** — separate free tier, separate quotas. Same OpenAI-compatible API, just swap `OPENROUTER_BASE_URL` → `https://api.groq.com/openai/v1`. Groq hosts Llama 3.3 70B + Gemma 2 9B free, no card.
3. **Migrate backend off Vercel** — Railway/Fly with residential proxies (Bright Data, ScraperAPI). Unlocks the other 3 portals too. ~1 day work after Railway signup.
4. **Manual capture** — open a browser, save the HTML of 5 listings from each portal, drop into `tests/fixtures/<portal>/sample-2.html` etc., run calibration against those. Bypasses anti-bot entirely. ~30 min.

Recommended order: `4 → 1 → 3` (manual capture for an immediate signal; OpenRouter credits to make LLM reliable; Railway later for production scrapes).

## Next actions

1. **(Tuning)** — Update `specs/trust-engine.md` with the proposed deltas + add escalating tiers + add MULTIPLE_FLAGS multiplier. Update `app/engine/trust_score.py` to match. Re-run calibration. Expected: synthetic scammy → "risky", clean fixtures → 90+. Effort: 1 hour.
2. **(RERA endpoint)** — Verify the live Karnataka RERA project-lookup URL with a real ID + browser. Effort: 15 min once we have a real ID.
3. **(Real URLs)** — Currently blocked on a combination of portal anti-bot (99acres, Housing, Magicbricks) + OpenRouter free-tier rate limits (NoBroker SPA needs LLM extraction). See "Real options" above.
4. **(Hosting)** — Migrate backend off Vercel so `httpx.get()` against the portals actually returns HTML. The whole pipeline is theoretical for the 3 hostile portals until that ships. Effort: 1 day after Railway signup.
