# PropCheck — Chrome Extension

Manifest V3 Chrome extension that overlays a Trust Score badge on every
listing card on Magicbricks, 99acres, Housing.com, and NoBroker, plus a
full sidebar report on detail pages. Calls `https://api.rohitraj.tech/v1/check`.

## Quick start

```bash
cd extension
npm install
npm run build
```

This produces `dist/`. To load it in Chrome:

1. Visit `chrome://extensions/`
2. Toggle **Developer mode** on (top-right)
3. Click **Load unpacked**
4. Select the `dist/` folder

The PropCheck icon appears in the toolbar. Visit any property listing on a
supported portal and you should see the badge / sidebar within a few seconds.

## Build a release ZIP

```bash
npm run build:zip
```

Produces `propcheck-extension-<version>.zip` in the extension directory,
ready for Chrome Web Store upload.

## Layout

```
extension/
├── manifest.json                Manifest V3
├── package.json                 dev/build scripts, no runtime deps
├── tsconfig.json                strict TS, ES2020, NodeNext modules
├── esbuild.config.mjs           bundles each entry to dist/
├── scripts/
│   ├── clean.mjs                rm -rf dist/
│   ├── generate-icons.mjs       hand-rolled PNG encoder for the 3 icons
│   └── zip.mjs                  hand-rolled ZIP encoder for release
├── public/
│   ├── icons/                   built by generate-icons.mjs
│   └── popup.html               toolbar popup HTML
└── src/
    ├── shared/                  the LOCKED contract (see specs/chrome-extension.md)
    │   ├── types.ts             CheckResponse, Flag, etc.
    │   ├── api.ts               submitCheck() + ApiError
    │   ├── cache.ts             24h chrome.storage.local cache + recents
    │   ├── styles.ts            design tokens + shadow-DOM CSS
    │   ├── badge.ts             renderBadge() — closed shadow root widget
    │   ├── sidebar.ts           mountSidebar() — 360px right-edge panel
    │   ├── url.ts               detectPortal, isListingDetailPage
    │   └── log.ts               scoped console logger
    ├── background/
    │   └── worker.ts            service worker (ESM, MV3 module worker)
    ├── popup/
    │   └── popup.ts             toolbar popup script
    └── content/
        ├── magicbricks.ts       reference content-script implementation
        ├── acres99.ts           per-portal content script
        ├── housing.ts           per-portal content script
        ├── nobroker.ts          per-portal content script
        └── _template.ts         skeleton for new portal scripts
```

## Inspecting logs

Each scope emits to the page's console with a `[propcheck:<scope>]` prefix.

- **Service worker logs**: `chrome://extensions/` → PropCheck card →
  *service worker* link.
- **Content-script logs**: open DevTools on the portal page (F12) and
  filter the console by `propcheck`.
- **Popup logs**: right-click the toolbar icon → *Inspect popup*.

## How it works

1. **Manifest** matches each of the four portals with a content script
   bundled to a single IIFE per portal.
2. The content script branches on `isListingDetailPage(window.location.href)`:
   - **Detail page**: shows a small loading badge top-right, calls
     `getCached → submitCheck → setCached`, then mounts the sidebar.
   - **Search results**: an `IntersectionObserver` watches listing cards
     and renders a placeholder badge in each card's top-right corner,
     fetches cache-first, then updates the badge in place.
3. The cache key is `chk:<sha1(url)[0..16]>` in `chrome.storage.local` with
   24h TTL. Lazy 7-day pruning runs on every `setCached` call.
4. The popup is a static HTML page with a "paste a URL" input (forwards to
   `propcheck.rohitraj.tech?url=...`) and a 5-entry recent-checks list.

## Privacy

The extension only sends the **current listing URL** to
`api.rohitraj.tech` — never page contents, never browsing history, never
other tabs. The popup footer reflects this and the manifest declares only
the four portals + our API in `host_permissions`.

## Adding a new portal

Copy `src/content/_template.ts` to `src/content/<portal>.ts`, set
`PORTAL_NAME` and `CARD_SELECTORS`, then add the bundle entry in
`esbuild.config.mjs` and the `content_scripts` block in `manifest.json`.
The shared contract in `src/shared/*` is locked — extend it via PR if
your portal genuinely needs something new.

## Type checking

```bash
npm run typecheck
```

`tsconfig.json` runs in `noEmit` mode; esbuild does the actual transpile.

## Notes & deviations from the spec

- **Icons**: instead of `canvas` or `sharp` (heavy or platform-specific),
  the icons are written by a hand-rolled PNG encoder in
  `scripts/generate-icons.mjs`. Three real PNGs (16, 48, 128) hit
  `public/icons/` on `npm run build:icons` and are copied to `dist/icons/`
  on `npm run build`. Rationale: 150 lines of Node, zero deps, works on
  every platform, deterministic output.
- **Service worker** uses ESM (MV3 supports it via `"type": "module"`);
  content scripts use IIFE because Chrome's content-script ESM support
  is unreliable.
- The bundled output excludes sourcemaps to keep the CWS package lean.
  Re-enable in `esbuild.config.mjs` if you need them locally.
