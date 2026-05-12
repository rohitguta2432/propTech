/**
 * Design tokens + shadow-DOM CSS strings.
 *
 * The badge and sidebar both inject these into their own ShadowRoot so the
 * host portal page can never override our visual identity. Tokens are
 * exported separately so content scripts can read individual colors without
 * parsing the CSS string.
 *
 * Tokens follow specs/design.md hybrid: cream surface, ink text, orange
 * brand mark, traffic-light score colors.
 */

export const tokens = {
  // Surface palette
  cream: "#faf9f5",
  ink: "#141413",
  orange: "#d97757",
  subtle: "#e8e6df",
  inkSoft: "rgba(20, 20, 19, 0.7)",
  inkMuted: "rgba(20, 20, 19, 0.55)",

  // Score colors
  safe: "#10B981",
  amber: "#F59E0B",
  risky: "#EF4444",

  // Score gradient backgrounds (specs/design.md anatomy)
  gradSafe: "linear-gradient(135deg, #ECFDF5, #D1FAE5)",
  gradAmber: "linear-gradient(135deg, #FFFBEB, #FEF3C7)",
  gradRisky: "linear-gradient(135deg, #FEF2F2, #FEE2E2)",
  gradLoading: "linear-gradient(135deg, #f5f4ee, #faf9f5)",

  // Severity pill colors
  sevHigh: "#EF4444",
  sevMedium: "#F59E0B",
  sevLow: "#94a3b8",
  sevPositive: "#10B981",

  fontSans:
    '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
  fontMono: 'ui-monospace, SFMono-Regular, "JetBrains Mono", "Fira Code", Menlo, Consolas, monospace',
} as const;

export type ScoreLabel = "safe" | "caution" | "risky";

export function gradientForLabel(label: ScoreLabel | null): string {
  switch (label) {
    case "safe":
      return tokens.gradSafe;
    case "caution":
      return tokens.gradAmber;
    case "risky":
      return tokens.gradRisky;
    default:
      return tokens.gradLoading;
  }
}

export function colorForLabel(label: ScoreLabel | null): string {
  switch (label) {
    case "safe":
      return tokens.safe;
    case "caution":
      return tokens.amber;
    case "risky":
      return tokens.risky;
    default:
      return tokens.inkMuted;
  }
}

/** Inject badge + sidebar styles into a closed shadow root. */
export function injectShadowStyles(root: ShadowRoot): void {
  const style = document.createElement("style");
  style.textContent = SHADOW_CSS;
  root.appendChild(style);
}

/**
 * Combined CSS for badge + sidebar. We inject the same blob in both;
 * unused rules are cheap and keeping a single source of truth simplifies
 * iteration.
 */
const SHADOW_CSS = `
:host {
  all: initial;
  font-family: ${tokens.fontSans};
  color: ${tokens.ink};
  line-height: 1.4;
  --cream: ${tokens.cream};
  --ink: ${tokens.ink};
  --orange: ${tokens.orange};
  --subtle: ${tokens.subtle};
  --safe: ${tokens.safe};
  --amber: ${tokens.amber};
  --risky: ${tokens.risky};
  --mono: ${tokens.fontMono};
}
* { box-sizing: border-box; }
button { font: inherit; cursor: pointer; }

/* --- Badge --- */
.badge {
  display: inline-flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  border-radius: 12px;
  border: 2px solid var(--ink);
  font-family: inherit;
  user-select: none;
  cursor: pointer;
  transition: transform 100ms ease-out, box-shadow 100ms ease-out;
  background: ${tokens.cream};
  text-align: center;
  padding: 6px 4px;
}
.badge:hover { transform: translateY(-1px); box-shadow: 0 2px 6px rgba(15,23,42,0.10); }
.badge.size-sm { width: 48px; height: 48px; padding: 4px 2px; }
.badge.size-md { width: 64px; height: 64px; }
.badge.size-lg { width: 120px; height: 120px; padding: 12px 8px; }
.badge[data-label="safe"]    { background: ${tokens.gradSafe}; border-color: ${tokens.safe}; }
.badge[data-label="caution"] { background: ${tokens.gradAmber}; border-color: ${tokens.amber}; }
.badge[data-label="risky"]   { background: ${tokens.gradRisky}; border-color: ${tokens.risky}; }
.badge[data-confidence="low"] {
  /* Engine couldn't get enough data to score — render as neutral, not a verdict. */
  background: ${tokens.gradLoading};
  border-color: var(--subtle);
  color: ${tokens.inkMuted};
}
.badge[data-confidence="low"] .score,
.badge[data-confidence="low"] .label { color: ${tokens.inkMuted}; }
.badge[data-confidence="low"].size-lg .label {
  /* "Not enough data" is longer than SAFE / CAUTION / RISKY; shrink to fit. */
  font-size: 11px;
  letter-spacing: 0;
  text-transform: none;
  font-weight: 600;
  line-height: 1.2;
}
.badge[data-loading="true"] {
  background: ${tokens.gradLoading};
  border-color: var(--subtle);
  cursor: progress;
}
.badge[data-loading="true"] .score::before {
  content: "";
  display: block;
  width: 60%;
  height: 18px;
  margin: 4px auto;
  border-radius: 6px;
  background: linear-gradient(90deg, #eceae3 25%, #d8d6cd 50%, #eceae3 75%);
  background-size: 200% 100%;
  animation: shimmer 1.4s linear infinite;
}
@keyframes shimmer { 0% { background-position: 200% 0; } 100% { background-position: -200% 0; } }
.badge .score {
  font-family: var(--mono);
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  color: var(--ink);
  line-height: 1;
}
.badge.size-sm .score { font-size: 16px; }
.badge.size-md .score { font-size: 22px; }
.badge.size-lg .score { font-size: 56px; }
.badge .label {
  font-family: inherit;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--ink);
  margin-top: 2px;
}
.badge.size-sm .label { font-size: 8px; }
.badge.size-md .label { font-size: 9px; }
.badge.size-lg .label { font-size: 13px; margin-top: 6px; }
.badge .brand {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  font-size: 8px;
  font-weight: 600;
  letter-spacing: 0.02em;
  color: ${tokens.inkMuted};
  margin-top: 3px;
}
.badge.size-sm .brand { display: none; }
.badge.size-lg .brand { font-size: 11px; margin-top: 8px; }
.badge .brand .mark {
  width: 8px; height: 8px;
}
.badge.size-lg .brand .mark { width: 12px; height: 12px; }

/* --- Sidebar --- */
.sidebar {
  position: fixed;
  top: 0;
  right: 0;
  width: 360px;
  height: 100vh;
  background: ${tokens.cream};
  border-left: 1px solid ${tokens.subtle};
  box-shadow: -8px 0 24px rgba(20, 20, 19, 0.10);
  display: flex;
  flex-direction: column;
  z-index: 2147483647;
  font-family: inherit;
  color: var(--ink);
}
.sidebar header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px;
  border-bottom: 1px solid var(--subtle);
  background: ${tokens.cream};
}
.sidebar .brand {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-weight: 700;
  font-size: 15px;
  letter-spacing: -0.01em;
}
.sidebar .brand .mark {
  width: 28px; height: 28px;
  background: var(--ink);
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
}
.sidebar .close {
  border: 0;
  background: transparent;
  color: ${tokens.inkMuted};
  font-size: 18px;
  width: 28px;
  height: 28px;
  border-radius: 6px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}
.sidebar .close:hover { background: var(--subtle); color: var(--ink); }
.sidebar .body {
  flex: 1;
  overflow-y: auto;
  padding: 18px 16px 24px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.sidebar .score-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  padding: 6px 0 2px;
}
.sidebar .summary {
  font-size: 13px;
  line-height: 1.5;
  color: ${tokens.inkSoft};
  text-align: center;
  margin-top: 8px;
}
.sidebar .property {
  background: #fff;
  border: 1px solid var(--subtle);
  border-radius: 12px;
  padding: 12px 14px;
}
.sidebar .property h3 {
  margin: 0 0 4px;
  font-size: 14px;
  font-weight: 600;
  letter-spacing: -0.01em;
}
.sidebar .property .meta {
  font-size: 12px;
  color: ${tokens.inkSoft};
  display: flex;
  flex-wrap: wrap;
  gap: 4px 8px;
}
.sidebar .property .meta span + span::before {
  content: "·";
  margin-right: 6px;
  color: ${tokens.inkMuted};
}
.sidebar .section-title {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  font-weight: 700;
  color: ${tokens.inkMuted};
  margin: 4px 0;
}
.sidebar .flag {
  background: #fff;
  border: 1px solid var(--subtle);
  border-radius: 12px;
  padding: 12px 14px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.sidebar .flag-row {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  justify-content: space-between;
}
.sidebar .flag .label {
  font-size: 13px;
  font-weight: 600;
}
.sidebar .flag .description {
  font-size: 12px;
  color: ${tokens.inkSoft};
  line-height: 1.5;
}
.sidebar .flag .source {
  font-size: 11px;
  color: ${tokens.inkMuted};
}
.sidebar .pill {
  display: inline-flex;
  align-items: center;
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  padding: 3px 8px;
  border-radius: 999px;
  color: #fff;
  flex-shrink: 0;
}
.sidebar .pill[data-sev="high"]     { background: ${tokens.sevHigh}; }
.sidebar .pill[data-sev="medium"]   { background: ${tokens.sevMedium}; }
.sidebar .pill[data-sev="low"]      { background: ${tokens.sevLow}; }
.sidebar .pill[data-sev="positive"] { background: ${tokens.sevPositive}; }
.sidebar .checklist {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.sidebar .checklist label {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  font-size: 13px;
  line-height: 1.5;
  cursor: pointer;
}
.sidebar .checklist input[type="checkbox"] {
  margin-top: 2px;
  accent-color: var(--ink);
  width: 16px;
  height: 16px;
}
.sidebar .checklist input:checked + span {
  text-decoration: line-through;
  color: ${tokens.inkMuted};
}
.sidebar .cta {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  background: var(--ink);
  color: var(--cream);
  text-decoration: none;
  font-size: 13px;
  font-weight: 600;
  padding: 10px 14px;
  border-radius: 8px;
  border: 0;
  width: 100%;
}
.sidebar .cta:hover { background: #000; }
.sidebar .empty {
  font-size: 12px;
  color: ${tokens.inkMuted};
  font-style: italic;
}
`;
