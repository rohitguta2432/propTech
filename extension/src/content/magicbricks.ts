/**
 * Magicbricks content script — reference implementation for Agent B.
 *
 * Two modes (specs/chrome-extension.md):
 *   - Detail page: extract listing URL → cache-first → mountSidebar.
 *     Show a small loading badge in the top-right while fetching.
 *   - Search results: IntersectionObserver on listing cards. For each
 *     visible card, find its detail-page <a>, render a placeholder badge,
 *     fetch (cache-first), update.
 *
 * Defensive: the entire body is wrapped in try/catch. Cleanup on pagehide:
 * disconnect observers and remove injected nodes.
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
} from "../shared/url.js";
import { createLogger } from "../shared/log.js";
import type { CheckResponse } from "../shared/types.js";

const log = createLogger("magicbricks");

const PORTAL = "magicbricks" as const;
const CARD_SELECTORS = [
  ".mb-srp__card",
  ".mb-srp__list--item",
  '[class*="mb-srp__card"]',
  '[class*="card"]',
];
const DETAIL_LINK_RE = PORTAL_LISTING_URL_RE.magicbricks;

// Per-page state, lifted to module scope so cleanup can reach it.
const seenCards = new WeakSet<Element>();
const inflight = new Map<string, Promise<CheckResponse | null>>();
let observer: IntersectionObserver | null = null;
const injectedNodes: HTMLElement[] = [];
let detailUnmount: (() => void) | null = null;

function trackNode(el: HTMLElement): void {
  injectedNodes.push(el);
}

/**
 * Single source of truth for "fetch this URL", cache-first. Dedupes
 * concurrent requests for the same URL. Returns null on hard failure
 * so callers never throw to the page.
 */
async function fetchReport(url: string): Promise<CheckResponse | null> {
  const existing = inflight.get(url);
  if (existing) return existing;

  const promise = (async () => {
    try {
      const cached = await getCached(url);
      if (cached) {
        log.debug("cache hit", url);
        return cached;
      }
      log.debug("cache miss → submit", url);
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

/**
 * Find the detail-page anchor inside a card. Tries semantic selectors
 * first, then falls back to any <a> whose href matches the portal regex.
 */
function findDetailLink(card: Element): { href: string; absolute: string } | null {
  const anchors = card.querySelectorAll<HTMLAnchorElement>("a[href]");
  for (const a of anchors) {
    const raw = a.getAttribute("href");
    if (!raw) continue;
    if (!DETAIL_LINK_RE.test(raw)) continue;
    const absolute = resolveHref(raw);
    if (!absolute) continue;
    if (!isListingDetailPage(absolute)) continue;
    return { href: raw, absolute };
  }
  return null;
}

/** Position the badge in the card's top-right; ensure relative parent. */
function attachCardBadge(card: HTMLElement, badge: HTMLElement): void {
  const cs = getComputedStyle(card);
  if (cs.position === "static") {
    card.style.position = "relative";
  }
  const wrapper = document.createElement("div");
  wrapper.style.cssText =
    "position: absolute; top: 8px; right: 8px; z-index: 9999; pointer-events: auto;";
  wrapper.appendChild(badge);
  card.appendChild(wrapper);
  trackNode(wrapper);
}

function showCardBadge(card: HTMLElement, listingUrl: string): void {
  const badge = renderBadge({
    size: "sm",
    score: null,
    label: null,
    onClick: () => {
      // Click on card badge → open propcheck.rohitraj.tech with the URL,
      // since we're on a listing-grid page (no sidebar host).
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
    if (!handle) return;
    if (!report) {
      // Leave shimmer; user can click to escape to web.
      return;
    }
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
        /* selector errors */
      }
    }
    if (cards.size === 0) {
      // Fallback: any <a> matching the detail-link regex; treat its parent
      // card-like ancestor as the host.
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
  // Re-scan on DOM mutation for SPA pagination — the observer is stable,
  // we just hand it new cards as they appear.
  const mo = new MutationObserver(() => {
    try {
      collect();
    } catch {
      /* ignore */
    }
  });
  mo.observe(document.body, { childList: true, subtree: true });
  // Park the mutation observer on the global cleanup list.
  cleanups.push(() => mo.disconnect());
}

const cleanups: Array<() => void> = [];

function showDetailLoadingBadge(): HTMLElement {
  const wrap = document.createElement("div");
  wrap.style.cssText =
    "position: fixed; top: 16px; right: 16px; z-index: 2147483646; pointer-events: auto;";
  const badge = renderBadge({ size: "md", score: null, label: null });
  wrap.appendChild(badge);
  document.body.appendChild(wrap);
  trackNode(wrap);
  return wrap;
}

async function runDetailMode(): Promise<void> {
  const url = window.location.href;
  log.info("detail mode", url);
  const loadingHost = showDetailLoadingBadge();
  const report = await fetchReport(url);
  loadingHost.remove();
  if (!report) {
    log.info("no report — skipping sidebar");
    return;
  }
  detailUnmount = mountSidebar(report);
}

function runSearchMode(): void {
  log.info("search mode", window.location.href);
  setupSearchObserver();
}

function teardown(): void {
  observer?.disconnect();
  observer = null;
  while (cleanups.length) {
    try {
      cleanups.pop()?.();
    } catch {
      /* ignore */
    }
  }
  for (const node of injectedNodes.splice(0)) {
    try {
      node.remove();
    } catch {
      /* ignore */
    }
  }
  if (detailUnmount) {
    try {
      detailUnmount();
    } catch {
      /* ignore */
    }
    detailUnmount = null;
  }
  inflight.clear();
}

// Single module-level try/catch — never throw to the host page.
try {
  if (detectPortal(window.location.href) !== PORTAL) {
    // Belt-and-braces: should never trip given manifest matches.
  } else if (isListingDetailPage(window.location.href)) {
    void runDetailMode();
  } else {
    runSearchMode();
  }
  window.addEventListener("pagehide", teardown, { once: true });
} catch (e) {
  // Swallow — the page must keep working even if PropCheck is broken.
  log.error("init failed", e);
}
