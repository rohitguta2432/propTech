/**
 * URL helpers — portal detection + detail-page heuristics.
 *
 * The portal regexes mirror `backend/app/parsers/router.py` so we never
 * route a URL the backend doesn't accept. Detail-page heuristics come
 * from the per-portal table in `specs/chrome-extension.md`.
 */

export type Portal = "magicbricks" | "99acres" | "housing" | "nobroker";

/** Hostname-based portal detection. Mirrors backend/app/parsers/<portal>.py. */
const PORTAL_HOST_RE: Array<{ portal: Portal; re: RegExp }> = [
  { portal: "magicbricks", re: /(^|\.)magicbricks\.com$/i },
  { portal: "99acres", re: /(^|\.)99acres\.com$/i },
  { portal: "housing", re: /(^|\.)housing\.com$/i },
  { portal: "nobroker", re: /(^|\.)nobroker\.in$/i },
];

export function detectPortal(url: string): Portal | null {
  let host: string;
  try {
    host = new URL(url).hostname;
  } catch {
    return null;
  }
  for (const { portal, re } of PORTAL_HOST_RE) {
    if (re.test(host)) return portal;
  }
  return null;
}

/**
 * Detail-page heuristics — per-portal pathname patterns drawn from
 * specs/chrome-extension.md. Returns true if the URL looks like a single
 * listing detail page (vs a search results / category page).
 */
export function isListingDetailPage(url: string): boolean {
  let parsed: URL;
  try {
    parsed = new URL(url);
  } catch {
    return false;
  }
  const path = parsed.pathname;
  const portal = detectPortal(url);
  switch (portal) {
    case "magicbricks":
      // /propertyDetails/<slug>/<id> or any URL with `pdpid-<id>`
      return /\/propertyDetails\//i.test(path) || /pdpid[-_][0-9A-Za-z]+/i.test(parsed.href);
    case "99acres":
      // ...-spid-XXXX or ...-pid-XXXX (search-result URLs use neither)
      return /-(spid|pid)-[A-Z0-9]+/i.test(path);
    case "housing":
      // /buy/projects/<...> or /in/buy/<...> or /rd/<id> / /ds/<id>
      return /\/buy\/projects\//i.test(path) || /\/in\/buy\//i.test(path) || /\/(rd|ds)\/[0-9a-zA-Z]+/i.test(path);
    case "nobroker":
      // /property/<hex> or trailing /<digits>/
      return /\/property\/[a-f0-9]{8,}/i.test(path) || /\/[0-9]{6,}\/?(?:[?#]|$)/i.test(path);
    default:
      return false;
  }
}

/**
 * Listing-URL regex per portal — used as the fallback when primary CSS
 * selectors miss. Matches both absolute and relative URLs.
 */
export const PORTAL_LISTING_URL_RE: Record<Portal, RegExp> = {
  magicbricks: /(?:https?:\/\/[^"'\s]*magicbricks\.com)?\/[^"'\s]*(?:propertyDetails|pdpid[-_])[^"'\s]*/i,
  "99acres": /(?:https?:\/\/[^"'\s]*99acres\.com)?\/[^"'\s]*-(?:spid|pid)-[A-Z0-9]+[^"'\s]*/i,
  housing: /(?:https?:\/\/[^"'\s]*housing\.com)?\/[^"'\s]*(?:\/buy\/projects\/|\/in\/buy\/|\/(?:rd|ds)\/[0-9a-zA-Z]+)[^"'\s]*/i,
  nobroker: /(?:https?:\/\/[^"'\s]*nobroker\.in)?\/[^"'\s]*\/property\/[a-f0-9]{8,}[^"'\s]*/i,
};

/** Resolve a possibly-relative href to absolute on the current portal. */
export function resolveHref(href: string | null | undefined): string | null {
  if (!href) return null;
  try {
    return new URL(href, window.location.href).href;
  } catch {
    return null;
  }
}
