# PropTech — Product Idea

A standalone PropTech startup. India-first. Bootstrap → angel → seed.

---

## One line

A free trust checker for Indian property listings. Paste a Magicbricks / 99acres / Housing.com / NoBroker link → get a 0–100 trust score in 30 seconds, plus exactly what's wrong and what to verify before paying anyone.

---

## What it does (concrete walkthrough)

Rohit sees a 3BHK in Whitefield on Magicbricks for ₹1.2 Cr. Looks great. He pastes the link into our tool. In 30 seconds he gets:

- **Trust score: 42 / 100 — Risky**
- Listed 4 times across 3 portals at 3 different prices (₹1.2 Cr, ₹1.35 Cr, ₹1.1 Cr) — broker games
- Photos appear on 7 other listings — likely stolen / generic
- Price is 22% below Whitefield 3BHK average — either a deal or bait
- RERA number doesn't match Karnataka RERA records
- Builder has 6 open complaints on RERA portal
- **Before paying anything**: visit in person, get sale deed, check property tax record, never pay token over UPI

That's the product. Nothing more, nothing less.

---

## Three surfaces, one backend

1. **Website** — paste a link, get a report.
2. **Chrome extension** — the score appears automatically next to every listing as you scroll Magicbricks / 99acres / Housing / NoBroker.
3. **WhatsApp bot** — forward a link to a number, get the report back as a chat reply.

Same engine powers all three.

---

## Who pays

| Customer | Pays | Why |
|---|---|---|
| **Buyers / renters** | Nothing. Free forever. | This is the brand promise — neutral, non-conflicted. |
| **Banks / lenders (B2B API)** | ₹50–200 per check | They spend ₹2K–5K verifying each home loan. We do the listing-fraud + builder-reputation slice in 1 second. **This is the real revenue line.** |
| **Pro users** | ₹499/year | Unlimited checks, price-change alerts, deep due-diligence reports. Volume play. |
| **Affiliates** | Background revenue | Home loans, legal services, title-check (partner with Landeed). |

---

## Why this exists

- **65%** of Indian buyers say they can't trust listings (Housing.com survey).
- **₹10K–₹2L** lost per scam victim. Fake-listing scams on Magicbricks / 99acres / OLX / Housing / NoBroker are the single biggest urban-rental fraud category.
- **Nobody neutral exists.** The portals can't police themselves — they earn from listings. Landeed does title verification (different stage). FlatX, PropHunt, PropEx are matching engines (different problem).
- **The trust moment is empty whitespace** in Indian PropTech.

---

## The moat

The dataset. Every check builds a scam-pattern database — stolen images, repeat-offender brokers, suspicious price patterns, fake RERA numbers, builder-complaint history. Year 2, we know more about Indian listing fraud than the portals do. **That dataset is the asset banks and RERA will pay for.**

---

## Top risks

1. **Portals push back** (rate-limit, legal). Mitigate: parse only on user submission, no caching their content, fair-use legal position, eventually pitch them as partners.
2. **Data quality grind.** Mitigate: explainable rules-based v1, surface confidence levels, manual review queue.
3. **Founder is not full-time technical.** Mitigate: lock team decision in Week 1 — solo + AI coding, hire dev, or co-founder.
4. **B2C in India doesn't pay.** Mitigate: free for users, B2B API is the engine.
5. **Existing PropTech players copy.** Mitigate: speed + neutral positioning. They can't be neutral — they sell listings.

---

## Files in this folder

```
proptech/
├── README.md             ← this doc (product idea + status)
├── 90-day-plan.md        ← week-by-week MVP path
├── landing-page.md       ← copy ready to paste into Framer / Webflow / Next.js
├── positioning.md        ← name candidates, taglines, brand voice
├── mockup/               ← interactive HTML design preview (open index.html)
├── specs/                ← technical specs — read before coding
│   ├── README.md
│   ├── architecture.md   ← system design, stack, deployment, cost
│   ├── design.md         ← visual identity, screens, components, wireframes
│   ├── database.md       ← Postgres schema with CREATE statements
│   ├── api.md            ← full API contract — endpoints, errors, rate limits
│   ├── trust-engine.md   ← scoring rules v1 (11 signals)
│   └── sprint-1.md       ← first 14-day development plan
└── backend/              ← FastAPI service (runnable today)
    ├── README.md         ← how to run locally
    ├── app/              ← source
    ├── requirements.txt
    ├── Dockerfile
    └── .env.example
```

**Reading order for new contributors:**
1. This README (product + status)
2. `specs/architecture.md` (the system)
3. `specs/api.md` + `specs/database.md` + `specs/trust-engine.md` (the building blocks)
4. `specs/sprint-1.md` (what to build first)
5. `backend/README.md` (how to run)

---

## Status

- **Date**: 2026-05-09
- **Stage**: Specs complete. Backend scaffold running locally on port 8000 with stubbed `/v1/check`. Sprint 1 ready to start.
- **Next decision**: name + domain, team model, funding model.
- **Next code task**: Sprint 1 Day 2 — Supabase setup + Alembic migrations (see `specs/sprint-1.md`).
