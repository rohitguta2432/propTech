/**
 * Per-portal content script template — Agent B copies this for
 * 99acres / housing / nobroker. Replace TODOs with the portal-specific
 * selectors and any portal quirks (lazy-loaded grids, infinite scroll,
 * SPA route changes that don't fire pagehide, etc.).
 *
 * The skeleton mirrors content/magicbricks.ts. If you find yourself
 * diverging more than 30%, talk to the foundation agent — it usually
 * means the shared contract needs an extension, not a fork.
 */

import { renderBadge, getBadgeHandle } from "../shared/badge.js";
import { mountSidebar } from "../shared/sidebar.js";
import { getCached, setCached, pushRecent } from "../shared/cache.js";
import { submitCheck, ApiError } from "../shared/api.js";
import {
  detectPortal,
  isListingDetailPage,
  PORTAL_LISTING_URL_RE,
  resolveHref,
  type Portal,
} from "../shared/url.js";
import { createLogger } from "../shared/log.js";
import type { CheckResponse } from "../shared/types.js";

// ─── Per-portal config — edit these three constants ─────────────────────────
const PORTAL_NAME: Portal = "99acres"; // TODO: change per portal
const log = createLogger(PORTAL_NAME);

/** Primary CSS selector list for listing cards on search-results pages. */
const CARD_SELECTORS: string[] = [
  // TODO: paste portal-specific selectors here.
  // 99acres example:
  // ".srpTuple_srpTupleBox", '[data-testid="srp-tile"]'
  // Housing example:
  // '[data-q="cardCarousel"]', ".css-1k5kf6m", '[itemtype$="Residence"]'
  // NoBroker example:
  // ".card-container", ".cardFlex"
];

/** Detail-page URL regex — re-use the shared one, no need to redefine. */
const DETAIL_LINK_RE = PORTAL_LISTING_URL_RE[PORTAL_NAME];

// ─── Below: identical skeleton to magicbricks.ts. Don't edit unless ────────
// ─── there's a portal-specific reason. ─────────────────────────────────────

const seenCards = new WeakSet<Element>();
const inflight = new Map<string, Promise<CheckResponse | null>>();
let observer: IntersectionObserver | null = null;
const injectedNodes: HTMLElement[] = [];
const cleanups: Array<() => void> = [];
let detailUnmount: (() => void) | null = null;

async function fetchReport(url: string): Promise<CheckResponse | null> {
  const existing = inflight.get(url);
  if (existing) return existing;
  const promise = (async () => {
    try {
      const cached = await getCached(url);
      if (cached) return cached;
      const report = await submitCheck(url);
      await setCached(url, report);
      void pushRecent(url, report).catch(() => {});
      return report;
    } catch (e) {
      if (e instanceof ApiError && e.status === 429) {
        log.warn(`rate-limited (retry after ${e.retryAfter ?? "?"}s)`);
      } else {
        log.warn("submit failed", e);
      }
      return null;
    } finally {
      inflight.delete(url);
    }
  })();
  inflight.set(url, promise);
  return promise;
}

function findDetailLink(card: Element): { absolute: string } | null {
  const anchors = card.querySelectorAll<HTMLAnchorElement>("a[href]");
  for (const a of anchors) {
    const raw = a.getAttribute("href");
    if (!raw || !DETAIL_LINK_RE.test(raw)) continue;
    const absolute = resolveHref(raw);
    if (!absolute) continue;
    if (!isListingDetailPage(absolute)) continue;
    return { absolute };
  }
  return null;
}

function attachCardBadge(card: HTMLElement, badge: HTMLElement): void {
  const cs = getComputedStyle(card);
  if (cs.position === "static") card.style.position = "relative";
  const wrap = document.createElement("div");
  wrap.style.cssText =
    "position: absolute; top: 8px; right: 8px; z-index: 9999; pointer-events: auto;";
  wrap.appendChild(badge);
  card.appendChild(wrap);
  injectedNodes.push(wrap);
}

function showCardBadge(card: HTMLElement, listingUrl: string): void {
  const badge = renderBadge({
    size: "sm",
    score: null,
    label: null,
    onClick: () => {
      try {
        chrome.runtime.sendMessage({ type: "OPEN_PROPCHECK_HOMEPAGE", url: listingUrl });
      } catch {
        window.open(
          `https://propcheck.rohitraj.tech/?url=${encodeURIComponent(listingUrl)}`,
          "_blank",
          "noopener",
        );
      }
    },
  });
  attachCardBadge(card, badge);
  void fetchReport(listingUrl).then((report) => {
    const handle = getBadgeHandle(badge as HTMLDivElement);
    if (!handle || !report) return;
    handle.update({ score: report.score, label: report.label });
  });
}

function setupSearchObserver(): void {
  if (!("IntersectionObserver" in window)) return;
  observer = new IntersectionObserver(
    (entries) => {
      for (const entry of entries) {
        if (!entry.isIntersecting) continue;
        const card = entry.target as HTMLElement;
        if (seenCards.has(card)) continue;
        const link = findDetailLink(card);
        if (!link) continue;
        seenCards.add(card);
        try {
          showCardBadge(card, link.absolute);
        } catch (e) {
          log.warn("card badge failed", e);
        }
      }
    },
    { rootMargin: "200px" },
  );

  const collect = (): void => {
    const cards = new Set<Element>();
    for (const sel of CARD_SELECTORS) {
      try {
        document.querySelectorAll(sel).forEach((el) => cards.add(el));
      } catch {
        /* ignore bad selector */
      }
    }
    if (cards.size === 0) {
      document.querySelectorAll<HTMLAnchorElement>("a[href]").forEach((a) => {
        const raw = a.getAttribute("href");
        if (!raw || !DETAIL_LINK_RE.test(raw)) return;
        const card = a.closest<HTMLElement>("article, li, div[class]");
        if (card) cards.add(card);
      });
    }
    cards.forEach((c) => {
      if (!seenCards.has(c)) observer?.observe(c);
    });
  };

  collect();
  const mo = new MutationObserver(() => {
    try {
      collect();
    } catch {
      /* ignore */
    }
  });
  mo.observe(document.body, { childList: true, subtree: true });
  cleanups.push(() => mo.disconnect());
}

function showDetailLoadingBadge(): HTMLElement {
  const wrap = document.createElement("div");
  wrap.style.cssText =
    "position: fixed; top: 16px; right: 16px; z-index: 2147483646; pointer-events: auto;";
  wrap.appendChild(renderBadge({ size: "md", score: null, label: null }));
  document.body.appendChild(wrap);
  injectedNodes.push(wrap);
  return wrap;
}

async function runDetailMode(): Promise<void> {
  const url = window.location.href;
  const loading = showDetailLoadingBadge();
  const report = await fetchReport(url);
  loading.remove();
  if (!report) return;
  detailUnmount = mountSidebar(report);
}

function teardown(): void {
  observer?.disconnect();
  observer = null;
  while (cleanups.length) {
    try { cleanups.pop()?.(); } catch { /* ignore */ }
  }
  for (const node of injectedNodes.splice(0)) {
    try { node.remove(); } catch { /* ignore */ }
  }
  if (detailUnmount) {
    try { detailUnmount(); } catch { /* ignore */ }
    detailUnmount = null;
  }
  inflight.clear();
}

try {
  if (detectPortal(window.location.href) !== PORTAL_NAME) {
    // wrong portal — bail
  } else if (isListingDetailPage(window.location.href)) {
    void runDetailMode();
  } else {
    setupSearchObserver();
  }
  window.addEventListener("pagehide", teardown, { once: true });
} catch (e) {
  log.error("init failed", e);
}
