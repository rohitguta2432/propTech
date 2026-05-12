/**
 * Shared types for content scripts. These signatures are LOCKED — Agent B's
 * portal content scripts (acres99, housing, nobroker) import directly from
 * here, so any change ripples through every surface. Mirrors the wire format
 * served by `POST /v1/check` and the types declared in `web/lib/api.ts`.
 */

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

export type ParseConfidence = "high" | "medium" | "low";

export interface Verifications {
  rera: { status: string } | null;
  image_match_count: number | null;
  locality_avg_price_per_sqft: number | null;
  price_delta_pct: number | null;
  listing_age_days: number | null;
  builder_open_complaints: number | null;
  parse_confidence?: ParseConfidence | null;
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
  // When "low", the engine refused to commit to a real numeric score —
  // surfaces should render "Not enough data" instead of the score value.
  parse_confidence?: ParseConfidence | null;
}

export type ScoreLabel = CheckResponse["label"];

/** Messages exchanged between content scripts / popup and the service worker. */
export type WorkerMessage =
  | { type: "OPEN_FULL_REPORT"; id: string }
  | { type: "OPEN_PROPCHECK_HOMEPAGE"; url?: string };
