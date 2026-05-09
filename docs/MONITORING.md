# Monitoring & Observability

We deliberately do not bake monitoring keys into the repo. When you're ready
to turn on Sentry / PostHog / Plausible, follow the wiring notes below.

---

## Sentry (errors, both surfaces)

### Backend (FastAPI on Vercel)

1. Sign up at [sentry.io](https://sentry.io), create a Python project named `propcheck-api`.
2. Copy the DSN.
3. In Vercel dashboard → Project `propcheck-api` → Settings → Environment Variables, add:
   - `SENTRY_DSN` = the DSN from Sentry.
4. Add to `backend/requirements.txt`:
   ```
   sentry-sdk[fastapi]==2.20.0
   ```
5. Add to `backend/app/main.py` near the top of the module (before `app = FastAPI(...)`):
   ```python
   import os
   import sentry_sdk
   if dsn := os.getenv("SENTRY_DSN"):
       sentry_sdk.init(
           dsn=dsn,
           traces_sample_rate=0.1,
           profiles_sample_rate=0.1,
           environment=os.getenv("ENV", "production"),
       )
   ```
6. Redeploy via `vercel deploy --prod`.

### Frontend (Next.js on Vercel)

1. In Sentry create a JavaScript project named `propcheck-web`. Copy the DSN.
2. In Vercel → `propcheck-app` → Environment Variables:
   - `NEXT_PUBLIC_SENTRY_DSN` = JS DSN.
3. Run `npx @sentry/wizard@latest -i nextjs` from `web/`. The wizard adds:
   - `sentry.client.config.ts`, `sentry.edge.config.ts`, `sentry.server.config.ts`
   - `next.config.mjs` updates
   - `.sentryclirc`
4. Redeploy.

---

## PostHog (product analytics)

1. Sign up at [posthog.com](https://posthog.com), copy the project API key.
2. In Vercel → `propcheck-app` → Environment Variables:
   - `NEXT_PUBLIC_POSTHOG_KEY` = the key.
   - `NEXT_PUBLIC_POSTHOG_HOST` = `https://app.posthog.com` (or self-host).
3. `cd web && npm install posthog-js`
4. Add to `web/app/layout.tsx` (client component wrapper):
   ```tsx
   "use client";
   import posthog from "posthog-js";
   import { useEffect } from "react";

   if (typeof window !== "undefined" && process.env.NEXT_PUBLIC_POSTHOG_KEY) {
     posthog.init(process.env.NEXT_PUBLIC_POSTHOG_KEY, {
       api_host: process.env.NEXT_PUBLIC_POSTHOG_HOST,
       capture_pageview: true,
     });
   }
   ```
   Wrap children in `<PostHogProvider client={posthog}>`.

---

## Plausible (cookieless web analytics — alternative to PostHog)

Cheaper, simpler, GDPR-clean. Less powerful than PostHog.

1. Sign up at [plausible.io](https://plausible.io), add domain `propcheck.rohitraj.tech`.
2. In `web/app/layout.tsx` add `<script defer data-domain="propcheck.rohitraj.tech" src="https://plausible.io/js/script.js" />` inside `<head>`.

---

## Better Stack / UptimeRobot (uptime + alerts)

Single endpoint health check from a third-party perspective.

1. Sign up at [betteruptime.com](https://betteruptime.com).
2. Add monitor: `GET https://api.rohitraj.tech/healthz`, expects 200.
3. Add monitor: `GET https://propcheck.rohitraj.tech/`, expects 200.
4. Wire to email or Slack for alerts.

---

## Vercel built-ins (free, already running)

These are on by default — visit the Vercel dashboard:

- **Deployment logs** — every request hits Vercel logs. Useful for ad-hoc debug.
- **Speed Insights** — Core Web Vitals from real users. Free on Hobby.
- **Web Analytics** — page views, top pages, devices. Free on Hobby.

Turn on Speed Insights + Web Analytics from Project → Settings → toggle on. No code change needed.

---

## What to watch first (in order of urgency)

1. **5xx error rate** on `/v1/check` (Sentry, or Vercel logs).
2. **Average response latency** (Vercel Speed Insights).
3. **Trust Score distribution** — are we over-flagging? (PostHog event with `score` property.)
4. **Feedback flag rate** — `/v1/feedback` row count divided by `/v1/check` count.
5. **Cache hit rate** — `cache_hit: true` ratio in `checks` table.
