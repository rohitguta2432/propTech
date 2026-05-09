# Chrome Extension Spec

The viral surface. Trust Score badge appears on every listing card on Magicbricks, 99acres, Housing.com, and NoBroker; full sidebar report on detail pages. Calls our existing `api.rohitraj.tech/v1/check`.

---

## Architecture (Manifest V3)

```
extension/
├── manifest.json                     ← V3 manifest
├── package.json                      ← npm scripts: build, build:zip, dev
├── tsconfig.json                     ← strict TS
├── esbuild.config.mjs                ← single bundle per content script + service worker
├── public/
│   ├── icons/icon-16.png             ← 16, 48, 128 px brand icons (PropCheck mark)
│   └── popup.html                    ← extension toolbar popup
├── src/
│   ├── shared/
│   │   ├── api.ts                    ← API client (POST /v1/check, error/429 handling)
│   │   ├── cache.ts                  ← chrome.storage.local 24h cache wrapper
│   │   ├── badge.ts                  ← Trust Score badge DOM renderer (vanilla)
│   │   ├── sidebar.ts                ← Full report sidebar DOM renderer (vanilla)
│   │   ├── styles.ts                 ← CSS-in-JS strings (Anthropic hybrid)
│   │   ├── url.ts                    ← Helpers: detectPortal, isListingDetailPage, etc.
│   │   ├── types.ts                  ← Re-exports from web/lib/api.ts shape
│   │   └── log.ts                    ← Lightweight scoped logger
│   ├── background/
│   │   └── worker.ts                 ← Service worker (chrome.runtime.onInstalled, message router)
│   ├── popup/
│   │   └── popup.ts                  ← Toolbar popup logic (recent checks, paste-and-check)
│   └── content/
│       ├── magicbricks.ts            ← Listing-card badge + detail-page sidebar
│       ├── acres99.ts
│       ├── housing.ts
│       └── nobroker.ts
└── dist/                             ← build output (gitignored)
```

---

## Two display modes

### 1. Badge mode (listing-card overlay)

When the user is on a search-results / listing-grid page, every listing card gets a small badge in its top-right corner.

- Size: 64×64px badge
- Renders: score number (mono) + RISKY/CAUTION/SAFE label + brand mark
- Loading state: shimmer placeholder while API call in-flight
- Cache hit: instant render
- Click: opens the sidebar with full report

### 2. Sidebar mode (listing-detail page)

When the URL matches a listing-detail page pattern, a 360px-wide sidebar slides in from the right.

- Sticky on the right edge (z-index 999999, doesn't break the page)
- Full report: large score badge + 4–6 red flags + checklist + "See full report" link to propcheck.rohitraj.tech
- Dismissible (✕ in the corner; remembered per-tab via sessionStorage)
- Loading state: skeleton while API call in-flight

---

## Shared interfaces (the contract for parallel agents)

All content scripts import from `src/shared/*`. These signatures are LOCKED — content-script agents implement against them, foundation agent implements them.

### `src/shared/types.ts`

```ts
export type Severity = "high" | "medium" | "low" | "positive";

export interface Flag {
  code: string;
  label: string;
  description: string;
  severity: Severity;
  evidence_urls: string[];
  source: string;
}

export interface PropertyInfo {
  portal: string;
  listing_id: string;
  title: string | null;
  price_inr: number | null;
  bhk: number | null;
  area_sqft: number | null;
  locality: string | null;
  city: string | null;
  state: string | null;
  rera_id: string | null;
  builder_name: string | null;
  listed_at: string | null;
}

export interface Verifications {
  rera: { status: string } | null;
  image_match_count: number | null;
  locality_avg_price_per_sqft: number | null;
  price_delta_pct: number | null;
  listing_age_days: number | null;
  builder_open_complaints: number | null;
}

export interface CheckResponse {
  id: string;
  score: number;
  label: "safe" | "caution" | "risky";
  summary: string;
  property: PropertyInfo;
  red_flags: Flag[];
  green_flags: Flag[];
  checklist: string[];
  verifications: Verifications;
  checked_at: string;
  cache_hit: boolean;
}
```

### `src/shared/api.ts`

```ts
export const API_BASE = "https://api.rohitraj.tech";

export async function submitCheck(url: string, signal?: AbortSignal): Promise<CheckResponse>;
// Calls POST /v1/check with x-extension UA marker so server logs surface=extension.
// Throws ApiError on non-2xx with .status and .detail.
```

### `src/shared/cache.ts`

```ts
export async function getCached(url: string): Promise<CheckResponse | null>;
// Returns cached report if <24h old (TTL = 86,400,000 ms).
export async function setCached(url: string, report: CheckResponse): Promise<void>;
// Stores in chrome.storage.local under key `chk:${url}` with timestamp.
```

### `src/shared/badge.ts`

```ts
export interface BadgeOpts {
  size: "sm" | "md" | "lg";
  score: number | null;        // null = loading
  label: "safe" | "caution" | "risky" | null;
  onClick?: (e: MouseEvent) => void;
}

export function renderBadge(opts: BadgeOpts): HTMLElement;
// Returns a self-contained <div> with embedded CSS (shadow DOM).
// Sizes: sm=48px, md=64px, lg=120px.
```

### `src/shared/sidebar.ts`

```ts
export function mountSidebar(report: CheckResponse, host?: HTMLElement): () => void;
// Mounts a 360px right-edge sidebar with the full report.
// Returns an unmount function.
// Skips remount if a sidebar already exists for the same report.id.
```

### `src/shared/url.ts`

```ts
export type Portal = "magicbricks" | "99acres" | "housing" | "nobroker";

export function detectPortal(url: string): Portal | null;
// Same regex set as backend's app/parsers/router.py.
export function isListingDetailPage(url: string): boolean;
// Heuristic: URL pattern matches a single-listing detail page (vs a search results page).
```

### Per-portal content script contract

Each `src/content/<portal>.ts` exports nothing; it runs at `document_idle` and:

1. Detects whether the current page is a search-results page or a detail page (heuristic: presence of grid containers or detail blocks).
2. **Search results**: `IntersectionObserver` on listing cards. When a card scrolls into view:
   - Extract its href (the listing URL).
   - Check cache (`getCached`). If hit, render badge immediately.
   - If miss, render loading badge, call `submitCheck(href)`, then update.
3. **Detail page**: extract the URL (`window.location.href`), call `submitCheck`, mount sidebar.
4. Dedup: never call `submitCheck` for the same URL twice within a 24h cache window.
5. Defensive selectors: try a primary CSS selector list, fall back to a heuristic (any `<a>` whose href matches the portal's listing URL pattern). Never throw.

### Per-portal CSS selectors (initial best-guess; tighten with real-page testing)

| Portal | Search-card selector | Detail-page check |
|---|---|---|
| Magicbricks | `.mb-srp__card`, `.mb-srp__list--item` | `pathname includes /propertyDetails/` |
| 99acres | `.srpTuple_srpTupleBox`, `[data-testid="srp-tile"]` | `pathname matches /-spid-` or `/-pid-` |
| Housing.com | `[data-q="cardCarousel"]`, `.css-1k5kf6m`, `[itemtype$="Residence"]` | `pathname includes /buy/projects/` or `/in/buy/` |
| NoBroker | `.card-container`, `.cardFlex` | `pathname matches /property/` |

---

## Manifest V3

```json
{
  "manifest_version": 3,
  "name": "PropCheck — Property Trust Score",
  "version": "0.1.0",
  "description": "0–100 trust score on every Indian property listing. Free, neutral, built for buyers.",
  "icons": { "16": "icons/icon-16.png", "48": "icons/icon-48.png", "128": "icons/icon-128.png" },
  "action": {
    "default_popup": "popup.html",
    "default_icon": { "16": "icons/icon-16.png", "48": "icons/icon-48.png" }
  },
  "background": { "service_worker": "background/worker.js", "type": "module" },
  "permissions": ["storage", "activeTab"],
  "host_permissions": [
    "https://*.magicbricks.com/*",
    "https://*.99acres.com/*",
    "https://*.housing.com/*",
    "https://*.nobroker.in/*",
    "https://api.rohitraj.tech/*"
  ],
  "content_scripts": [
    { "matches": ["https://*.magicbricks.com/*"], "js": ["content/magicbricks.js"], "run_at": "document_idle" },
    { "matches": ["https://*.99acres.com/*"], "js": ["content/acres99.js"], "run_at": "document_idle" },
    { "matches": ["https://*.housing.com/*"], "js": ["content/housing.js"], "run_at": "document_idle" },
    { "matches": ["https://*.nobroker.in/*"], "js": ["content/nobroker.js"], "run_at": "document_idle" }
  ]
}
```

---

## Visual identity

Same Anthropic hybrid as the web app:

- Cream `#faf9f5` surface, ink `#141413` text, orange `#d97757` for the brand mark.
- Score gradients (functional traffic-light, never decorative): safe `#10B981`, amber `#F59E0B`, risky `#EF4444`.
- Headings: Poppins (loaded via the extension popup; in-page badges use system-ui to avoid font-loading flash).
- Score numbers: JetBrains Mono.
- Badges use **Shadow DOM** for full style isolation from the host page.

---

## Privacy

The extension only sends the **current listing URL** to `api.rohitraj.tech` — never the page contents, never history, never tabs other than the active listing. Document this prominently in the popup. Listed in `permissions` only because we use `storage` (cache) and `host_permissions` for the four portals + our API.

---

## Build + distribution

- **Bundler**: esbuild via `esbuild.config.mjs` (one bundle per content-script + service worker + popup).
- **Output**: `dist/` (gitignored). Contains all assets ready for `chrome://extensions/` "Load unpacked".
- **Release ZIP**: `npm run build:zip` produces `propcheck-extension-<version>.zip` for Chrome Web Store upload.
- **CI**: GitHub Actions builds the extension on every push to main and uploads the ZIP as a release artifact (Phase 8 stretch goal).

---

## Out of scope at v0.1

- Firefox / Edge variants (Manifest V3 is mostly cross-compatible; ship to Chrome Web Store first, port later).
- Listing-search-page badge **on hover** vs **on visible** — start with on-visible; revisit if API quota becomes a concern.
- User auth in the extension (Pro/B2B keys ride in popup later).
- Notifications (chrome.notifications API) for high-risk listings — Phase 9 candidate.

---

## Done when

1. `cd extension && npm install && npm run build` produces a working `dist/`.
2. `chrome://extensions/` → Load unpacked → `dist/` loads cleanly with no errors.
3. Visiting a Magicbricks listing detail page shows the sidebar with a real Trust Score within 5 seconds.
4. Visiting a Magicbricks search-results page shows badges on at least 5 listing cards.
5. Same for 99acres, Housing.com, NoBroker (one detail page + search page each).
6. Popup shows the brand and a "Check a URL" input that opens propcheck.rohitraj.tech with the URL prefilled.
7. `extension/README.md` documents how to load unpacked + how to build a release ZIP.
