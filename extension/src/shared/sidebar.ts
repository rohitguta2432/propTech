/**
 * Detail-page sidebar — fixed-position 360px panel on the right edge.
 *
 * Renders:
 *   - Header (brand mark + close)
 *   - Large score badge
 *   - Property summary block
 *   - Up to 6 red flags with severity pills
 *   - Pre-purchase checklist (persisted to chrome.storage.local per report id)
 *   - "See full report" CTA → propcheck.rohitraj.tech/check/<id>
 *
 * Returns an unmount() function. If a sidebar for the same report.id is
 * already mounted, returns its existing unmount instead of double-mounting.
 */

import { injectShadowStyles } from "./styles.js";
import { renderBadge } from "./badge.js";
import type { CheckResponse, Flag } from "./types.js";
import { createLogger } from "./log.js";

const log = createLogger("sidebar");

let activeReportId: string | null = null;
let activeUnmount: (() => void) | null = null;

const FULL_REPORT_BASE = "https://propcheck.rohitraj.tech/check/";
const HOST_TAG = "propcheck-sidebar-root";
const CHECKLIST_KEY_PREFIX = "checklist:";
const MAX_RED_FLAGS = 6;

function fmtINR(n: number | null): string {
  if (n == null) return "";
  if (n >= 10_000_000) return `Rs ${(n / 10_000_000).toFixed(2)} Cr`;
  if (n >= 100_000) return `Rs ${(n / 100_000).toFixed(2)} L`;
  return `Rs ${n.toLocaleString("en-IN")}`;
}

function setText(el: HTMLElement, text: string): void {
  el.textContent = text;
}

function flagCard(flag: Flag): HTMLElement {
  const card = document.createElement("div");
  card.className = "flag";
  const row = document.createElement("div");
  row.className = "flag-row";
  const label = document.createElement("div");
  label.className = "label";
  setText(label, flag.label);
  const pill = document.createElement("span");
  pill.className = "pill";
  pill.dataset.sev = flag.severity;
  setText(pill, flag.severity);
  row.appendChild(label);
  row.appendChild(pill);
  const desc = document.createElement("div");
  desc.className = "description";
  setText(desc, flag.description);
  card.appendChild(row);
  card.appendChild(desc);
  if (flag.source) {
    const src = document.createElement("div");
    src.className = "source";
    setText(src, `Source: ${flag.source}`);
    card.appendChild(src);
  }
  return card;
}

async function loadChecklistState(reportId: string): Promise<Record<string, boolean>> {
  if (!chrome?.storage?.local) return {};
  try {
    const key = CHECKLIST_KEY_PREFIX + reportId;
    const result = await chrome.storage.local.get(key);
    const state = result[key];
    return state && typeof state === "object" ? (state as Record<string, boolean>) : {};
  } catch {
    return {};
  }
}

async function saveChecklistState(
  reportId: string,
  state: Record<string, boolean>,
): Promise<void> {
  if (!chrome?.storage?.local) return;
  try {
    const key = CHECKLIST_KEY_PREFIX + reportId;
    await chrome.storage.local.set({ [key]: state });
  } catch (e) {
    log.warn("checklist save failed", e);
  }
}

function buildPropertyBlock(report: CheckResponse): HTMLElement {
  const wrap = document.createElement("div");
  wrap.className = "property";
  const title = document.createElement("h3");
  const p = report.property;
  setText(
    title,
    p.title ?? `${p.bhk ? p.bhk + " BHK " : ""}${p.locality ?? p.city ?? "Property"}`,
  );
  wrap.appendChild(title);
  const meta = document.createElement("div");
  meta.className = "meta";
  const bits: string[] = [];
  if (p.price_inr != null) bits.push(fmtINR(p.price_inr));
  if (p.bhk != null) bits.push(`${p.bhk} BHK`);
  if (p.area_sqft != null) bits.push(`${p.area_sqft.toLocaleString("en-IN")} sqft`);
  if (p.locality) bits.push(p.locality);
  if (p.city && p.city !== p.locality) bits.push(p.city);
  if (bits.length === 0) bits.push("Listing details unavailable");
  for (const b of bits) {
    const span = document.createElement("span");
    setText(span, b);
    meta.appendChild(span);
  }
  wrap.appendChild(meta);
  return wrap;
}

/**
 * Mount the sidebar. Returns an unmount() function.
 * If a sidebar for the same report.id is already mounted, returns its
 * unmount and skips re-mount.
 */
export function mountSidebar(
  report: CheckResponse,
  hostEl?: HTMLElement,
): () => void {
  if (activeReportId === report.id && activeUnmount) {
    return activeUnmount;
  }
  // Different id: tear down the old one first
  if (activeUnmount) activeUnmount();

  const host = document.createElement(HOST_TAG);
  host.style.cssText = "all: initial; position: fixed; inset: 0 0 0 auto; width: 360px; z-index: 2147483647;";
  const root = host.attachShadow({ mode: "closed" });
  injectShadowStyles(root);

  const sidebar = document.createElement("aside");
  sidebar.className = "sidebar";
  sidebar.setAttribute("aria-label", "PropCheck trust report");

  // Header
  const header = document.createElement("header");
  const brand = document.createElement("div");
  brand.className = "brand";
  brand.innerHTML = `
    <span class="mark">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#d97757" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
        <path d="M9 12l2 2 4-4"></path>
        <circle cx="12" cy="12" r="10"></circle>
      </svg>
    </span>
    <span>PropCheck</span>
  `;
  const close = document.createElement("button");
  close.type = "button";
  close.className = "close";
  close.setAttribute("aria-label", "Close PropCheck sidebar");
  setText(close, "✕");
  header.appendChild(brand);
  header.appendChild(close);

  // Body
  const body = document.createElement("div");
  body.className = "body";

  // Score card with large badge. On a low-confidence parse the badge
  // primitive renders "— / Not enough data" instead of the (meaningless)
  // 50/CAUTION verdict the engine emits as a placeholder.
  const scoreCard = document.createElement("div");
  scoreCard.className = "score-card";
  const badge = renderBadge({
    size: "lg",
    score: report.score,
    label: report.label,
    confidence: report.parse_confidence ?? null,
  });
  scoreCard.appendChild(badge);
  if (report.summary) {
    const summary = document.createElement("p");
    summary.className = "summary";
    setText(summary, report.summary);
    scoreCard.appendChild(summary);
  }
  body.appendChild(scoreCard);

  // Property
  body.appendChild(buildPropertyBlock(report));

  // Red flags (max 6)
  const flagsTitle = document.createElement("div");
  flagsTitle.className = "section-title";
  setText(flagsTitle, `Red flags (${report.red_flags.length})`);
  body.appendChild(flagsTitle);
  if (report.red_flags.length === 0) {
    const empty = document.createElement("div");
    empty.className = "empty";
    setText(empty, "None found.");
    body.appendChild(empty);
  } else {
    for (const flag of report.red_flags.slice(0, MAX_RED_FLAGS)) {
      body.appendChild(flagCard(flag));
    }
  }

  // Checklist
  if (report.checklist?.length) {
    const checklistTitle = document.createElement("div");
    checklistTitle.className = "section-title";
    setText(checklistTitle, "Pre-purchase checklist");
    body.appendChild(checklistTitle);

    const checklist = document.createElement("div");
    checklist.className = "checklist";
    body.appendChild(checklist);

    void loadChecklistState(report.id).then((state) => {
      report.checklist.forEach((item, i) => {
        const id = `chk-${i}`;
        const lbl = document.createElement("label");
        const input = document.createElement("input");
        input.type = "checkbox";
        input.id = id;
        input.checked = !!state[id];
        const span = document.createElement("span");
        setText(span, item);
        lbl.appendChild(input);
        lbl.appendChild(span);
        checklist.appendChild(lbl);
        input.addEventListener("change", () => {
          state[id] = input.checked;
          void saveChecklistState(report.id, state);
        });
      });
    });
  }

  // CTA
  const cta = document.createElement("button");
  cta.type = "button";
  cta.className = "cta";
  setText(cta, "See full report ↗");
  body.appendChild(cta);

  sidebar.appendChild(header);
  sidebar.appendChild(body);
  root.appendChild(sidebar);

  // Wire interactions
  const onClose = (): void => {
    unmount();
  };
  const onCta = (): void => {
    const target = `${FULL_REPORT_BASE}${encodeURIComponent(report.id)}`;
    try {
      // Service worker handles tab creation when available; fall back to
      // window.open for popup-style contexts.
      if (chrome?.runtime?.id) {
        chrome.runtime.sendMessage({ type: "OPEN_FULL_REPORT", id: report.id });
      } else {
        window.open(target, "_blank", "noopener");
      }
    } catch {
      window.open(target, "_blank", "noopener");
    }
  };
  close.addEventListener("click", onClose);
  cta.addEventListener("click", onCta);

  // Mount to host or document.body
  (hostEl ?? document.body).appendChild(host);

  let unmounted = false;
  const unmount = (): void => {
    if (unmounted) return;
    unmounted = true;
    close.removeEventListener("click", onClose);
    cta.removeEventListener("click", onCta);
    host.remove();
    if (activeReportId === report.id) {
      activeReportId = null;
      activeUnmount = null;
    }
  };

  activeReportId = report.id;
  activeUnmount = unmount;
  return unmount;
}
