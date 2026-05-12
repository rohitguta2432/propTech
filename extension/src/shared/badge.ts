/**
 * Trust Score badge — closed Shadow DOM widget.
 *
 * Sizes: sm=48px (search-card overlay corner), md=64px (default card),
 * lg=120px (sidebar header). Loading state shimmers the score area.
 *
 * The wrapper element is appended to the host page; the badge itself
 * lives inside a closed shadow root so the host page cannot inspect or
 * style it. We expose `update()` and `dispose()` via the WeakMap below
 * so callers can flip a loading badge into a real badge in place without
 * recreating the DOM.
 */

import { injectShadowStyles } from "./styles.js";
import type { ParseConfidence, ScoreLabel } from "./types.js";

export interface BadgeOpts {
  size: "sm" | "md" | "lg";
  score: number | null;
  label: ScoreLabel | null;
  /**
   * When "low", the badge renders an "incomplete" state — "—" / "?" for the
   * numeric score and "Not enough data" / "?" for the label. This overrides
   * the regular score+label rendering even when both are non-null, because
   * the trust engine emits a neutral score=50 for low-confidence parses
   * and the badge must not show that as if it were a real verdict.
   * "high" / "medium" / null / undefined all render the normal score+label.
   */
  confidence?: ParseConfidence | null;
  onClick?: (e: MouseEvent) => void;
}

export interface BadgeHandle {
  el: HTMLDivElement;
  update(opts: Partial<BadgeOpts>): void;
  dispose(): void;
}

const handles = new WeakMap<HTMLDivElement, BadgeHandle>();

const BRAND_MARK_SVG = `
<svg class="mark" viewBox="0 0 24 24" fill="none" stroke="#d97757" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
  <path d="M9 12l2 2 4-4"></path>
  <circle cx="12" cy="12" r="10"></circle>
</svg>`;

function labelText(label: ScoreLabel | null): string {
  switch (label) {
    case "safe":
      return "SAFE";
    case "caution":
      return "CAUTION";
    case "risky":
      return "RISKY";
    default:
      return "";
  }
}

function ariaLabel(
  score: number | null,
  label: ScoreLabel | null,
  confidence: ParseConfidence | null | undefined,
): string {
  if (confidence === "low") {
    return "PropCheck: not enough data to score this listing";
  }
  if (score == null || label == null) return "PropCheck Trust Score loading";
  return `PropCheck Trust Score ${score} of 100, ${labelText(label)}`;
}

/**
 * Render a self-contained badge. Returns the wrapper div; attach to the
 * host page wherever you want it (top-right of a card, sidebar header, etc).
 */
export function renderBadge(opts: BadgeOpts): HTMLDivElement {
  const wrapper = document.createElement("div");
  wrapper.className = "propcheck-badge-host";
  wrapper.style.cssText = "all: initial; display: inline-block;";
  // Closed shadow root: host page cannot reach into our subtree
  const root = wrapper.attachShadow({ mode: "closed" });
  injectShadowStyles(root);

  const badge = document.createElement("button");
  badge.type = "button";
  badge.className = `badge size-${opts.size}`;
  badge.setAttribute("role", "img");

  const score = document.createElement("div");
  score.className = "score";

  const label = document.createElement("div");
  label.className = "label";

  const brand = document.createElement("div");
  brand.className = "brand";
  brand.innerHTML = `${BRAND_MARK_SVG}<span>PropCheck</span>`;

  badge.appendChild(score);
  badge.appendChild(label);
  badge.appendChild(brand);
  root.appendChild(badge);

  const apply = (next: BadgeOpts): void => {
    if (next.confidence === "low") {
      // Engine refused to commit to a numeric score. Don't render one.
      delete badge.dataset.loading;
      delete badge.dataset.label;
      badge.dataset.confidence = "low";
      // sm/md sizes can't fit "Not enough data" — use a glyph instead.
      score.textContent = next.size === "lg" ? "—" : "?";
      label.textContent = next.size === "lg" ? "Not enough data" : "?";
    } else if (next.score == null || next.label == null) {
      badge.dataset.loading = "true";
      delete badge.dataset.label;
      delete badge.dataset.confidence;
      score.textContent = "";
      label.textContent = "";
    } else {
      delete badge.dataset.loading;
      delete badge.dataset.confidence;
      badge.dataset.label = next.label;
      score.textContent = String(next.score);
      label.textContent = labelText(next.label);
    }
    badge.setAttribute("aria-label", ariaLabel(next.score, next.label, next.confidence));
  };

  let click = opts.onClick;
  const onClick = (e: MouseEvent): void => {
    e.preventDefault();
    e.stopPropagation();
    click?.(e);
  };
  badge.addEventListener("click", onClick);

  apply(opts);

  const handle: BadgeHandle = {
    el: wrapper,
    update(next: Partial<BadgeOpts>) {
      const merged: BadgeOpts = {
        size: opts.size,
        score: next.score !== undefined ? next.score : opts.score,
        label: next.label !== undefined ? next.label : opts.label,
        confidence:
          next.confidence !== undefined ? next.confidence : opts.confidence,
        onClick: opts.onClick,
      };
      if (next.onClick !== undefined) click = next.onClick;
      Object.assign(opts, merged);
      apply(merged);
    },
    dispose() {
      badge.removeEventListener("click", onClick);
      wrapper.remove();
      handles.delete(wrapper);
    },
  };
  handles.set(wrapper, handle);
  return wrapper;
}

/** Look up the handle for a previously rendered badge wrapper, if any. */
export function getBadgeHandle(el: HTMLDivElement): BadgeHandle | undefined {
  return handles.get(el);
}
