/**
 * Housing.com content script — same shape as magicbricks reference.
 *
 * Two modes (specs/chrome-extension.md):
 *   - Detail page: extract listing URL → cache-first → mountSidebar.
 *   - Search results: IntersectionObserver on listing cards. For each
 *     visible card, find its detail-page <a>, render a placeholder badge,
 *     fetch (cache-first), update via getBadgeHandle().
 *
 * Defensive: module body wrapped in try/catch. Cleanup on pagehide.
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

const log = createLogger("housing");

const PORTAL = "housing" as const;
const CARD_SELECTORS = [
  '[data-q="cardCarousel"]',
  '[itemtype$="Residence"]',
  'a[href*="/buy/projects/"]',
  ".css-1k5kf6m",
  '[class*="ProjectCard"]',
];
const DETAIL_LINK_RE = PORTAL_LISTING_URL_RE.housing;

const seenCards = new WeakSet<Element>();
const inflight = new Map<string, Promise<CheckResponse | null>>();
let observer: IntersectionObserver | null = null;
const injectedNodes: HTMLElement[] = [];
const cleanups: Array<() => void> = [];
let detailUnmount: (() => void) | null = null;

function trackNode(el: HTMLElement): void {
  injectedNodes.push(el);
}

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

function findDetailLink(card: Element): { href: string; absolute: string } | null {
  const candidates: HTMLAnchorElement[] = [];
  if (card instanceof HTMLAnchorElement) candidates.push(card);
  card.querySelectorAll<HTMLAnchorElement>("a[href]").forEach((a) => candidates.push(a));
  for (const a of candidates) {
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
        /* selector errors */
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
  log.error("init failed", e);
}
