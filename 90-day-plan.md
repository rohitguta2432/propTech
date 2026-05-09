# 90-Day MVP Plan

Goal at end of 90 days: 1,000+ web checks/week, 100+ Chrome extension installs, 200+ WhatsApp users, 1 viral story or press mention, 1 city covered properly (Bangalore).

---

## Scope lock — pick once, don't change

- **Cities at launch**: Bangalore only. Add Mumbai/Delhi/Pune/Hyderabad in Months 4–6.
- **Portals at launch**: Magicbricks, 99acres, Housing.com, NoBroker. *(In that order — MB has the highest scam-search volume.)*
- **RERA states at launch**: Karnataka only.
- **Property types**: residential sale + rental. No commercial / land at launch.
- **Languages**: English at launch. Hindi UI in Month 4. Kannada later.

---

## Week-by-week

### Weeks 1–2 — Setup + brand

| Task | Owner | Output |
|---|---|---|
| Pick name + buy `.in` domain | You | Domain in hand |
| Set up Google Workspace email + landing waitlist (Carrd or Framer) | You | `hello@[domain].in` + waitlist live |
| Lock team model: solo + AI coding / hire dev / co-founder | You | Decision in writing |
| Wireframe the web tool (Figma or paper) | You | 3 screens: paste, report, signup |
| Write the landing page (use `landing-page.md`) | You | Live waitlist page |
| Open social handles (Twitter, LinkedIn, Instagram) | You | Handles reserved |
| Soft-mention to 5 trusted friends — get reactions | You | 5 written reactions |

### Weeks 3–6 — Web tool MVP

| Task | Output |
|---|---|
| Backend: Python/FastAPI + Postgres + Redis | API skeleton |
| URL parser for 4 portals (HTML scrape on user submission only — no bulk crawling) | Parser tested on 50 real URLs each |
| Karnataka RERA API integration | Live RERA cross-check |
| Bangalore locality price index (scrape once, cache, manual refresh monthly) | Price benchmark per locality |
| Image reverse search via Google Vision or TinEye API | Stolen-image detection |
| Trust Score v1 — pure rules-based, no ML | Score engine that returns 0–100 + reasons |
| Frontend: Next.js + Tailwind, single page (paste → report) | Live web tool at `[domain].in/check` |
| 5 SEO landing pages: "magicbricks scam check", "99acres listing verify", "RERA Karnataka lookup", "fair price Bangalore [locality]", "is this property real" | Indexed in Google |
| Privacy policy + Terms (use a template) | Compliance done |
| Analytics: PostHog or Plausible | Funnel tracked |

### Weeks 7–9 — WhatsApp bot

| Task | Output |
|---|---|
| Twilio sandbox setup → WABA when ready | WhatsApp number live |
| Webhook to existing backend | Same engine, new surface |
| Chat UX: paste link → 1-screen verdict | Conversation tested with 10 friends |
| Soft launch on Twitter/LinkedIn/Reddit | First 100 users |
| Add "share this report" deep link | Forwarding works |

### Weeks 10–12 — Chrome extension + public launch

| Task | Output |
|---|---|
| Chrome extension Manifest V3 | Loads on the 4 portals |
| Content script: inject Trust Score next to listing title | Score visible inline |
| Background script: call backend API on page load | <2s response |
| Submit to Chrome Web Store (allow 5–10 days for review) | Live in store |
| **Public launch day** | Product Hunt + r/india + r/bangalore + Twitter thread + 5 property Telegram groups |
| Press outreach: YourStory, Inc42, Moneylife, The Ken (cold pitch) | At least 1 reply |
| First 1,000 users | Hit goal |

---

## Targets at end of 90 days

| Metric | Target |
|---|---|
| Unique web checks per week | 1,000+ |
| Chrome extension installs | 100+ |
| WhatsApp bot users | 200+ |
| Cities covered | 1 (Bangalore) |
| Portals supported | 4 |
| Press / viral story | At least 1 |
| Email waitlist | 2,000+ |
| Cost so far | ≤ ₹3L |

---

## Tech stack (lean)

- **Backend**: Python 3.12 + FastAPI
- **DB**: Postgres (Supabase free tier OK at start) + Redis (Upstash)
- **Frontend web**: Next.js 14 + Tailwind + shadcn/ui
- **Chrome extension**: TypeScript + Manifest V3 + content script
- **WhatsApp**: Twilio sandbox → WhatsApp Business API
- **Scraping**: Playwright + rotating residential proxies (Bright Data / Oxylabs) — only on user submission
- **Image hashing**: pHash + Google Vision API
- **LLM helpers** (optional, for parsing unstructured listing fields): Claude Haiku
- **Hosting**: Vercel (frontend) + Railway / Fly.io (backend)
- **Analytics**: PostHog or Plausible
- **Email**: Resend
- **Auth (when needed)**: Clerk or Supabase Auth

Total infra cost in first 90 days: ~₹15K–25K/month. Domain + Twilio + tools ~₹10K.

---

## Cost estimate (90 days)

| Item | ₹ |
|---|---|
| Domain + hosting + SaaS tools | 30,000 |
| Twilio + WhatsApp sandbox | 10,000 |
| Image search API (Google Vision) | 15,000 |
| Proxies (Bright Data) | 30,000 |
| Designer (logo + brand kit, freelance) | 25,000 |
| Lawyer (privacy policy, terms, IP) | 25,000 |
| **If hiring 1 dev (BLR, ₹2L/month × 3)** | 6,00,000 |
| **If solo + AI coding** | 0 |
| **Total (with dev hire)** | ~₹7.4L |
| **Total (solo)** | ~₹1.4L |

---

## What I need from you (founder) — Week 1

1. **Pick name + domain.** 4 hours, decision-making block.
2. **Decide team model.** Solo, hire, or co-founder. Lock it.
3. **Decide funding.** Bootstrap from MyFinancial revenue / savings, or raise angel money first.
4. **Talk to 10 recent home buyers.** Ask: "When checking listings, what scared you? What did you wish you had?" Use their words for the landing page.
5. **Build a 60-second click-through demo** in Figma. Use it for early feedback + future fundraising.

These 5 unblock everything. Without them, no amount of building matters.

---

## What I'm consciously NOT doing in 90 days

- No paid ads. No Google/Meta spend until organic baseline is set.
- No mobile app. Web + extension + WhatsApp covers 95% of usage.
- No Tier-2 cities. Bangalore until quality is rock-solid.
- No commercial / land / plots. Residential only.
- No white-label / B2B SaaS. Wait for B2B API revenue line.
- No fundraising. Build first 90 days on bootstrap. Raise from a position of traction, not slides.

These are the things that look productive but kill focus.

---

## Day 91 — review and decide

At end of 90 days, three possible decisions:

1. **Working** (hit targets, growing weekly) → start Pre-Seed conversations, expand to Mumbai + Delhi.
2. **Almost** (some traction, some friction) → 30-day extension, fix the funnel before scaling.
3. **Not working** (no organic pull, users not retained) → kill the project, write a public post-mortem, move on. No sunk-cost continuation.

Set this checkpoint in the calendar now. **2026-08-07.**
