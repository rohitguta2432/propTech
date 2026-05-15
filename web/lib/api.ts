export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE || "https://propcheck-api.vercel.app";

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
  title?: string | null;
  price_inr?: number | null;
  bhk?: number | null;
  area_sqft?: number | null;
  locality?: string | null;
  city?: string | null;
  state?: string | null;
  rera_id?: string | null;
  builder_name?: string | null;
  listed_at?: string | null;
}

export type ParseConfidence = "high" | "medium" | "low";

export interface Verifications {
  rera?: Record<string, unknown> | null;
  image_match_count?: number | null;
  locality_avg_price_per_sqft?: number | null;
  price_delta_pct?: number | null;
  listing_age_days?: number | null;
  builder_open_complaints?: number | null;
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
  // the surfaces should render "Not enough data" instead of the score.
  parse_confidence?: ParseConfidence | null;
}

export async function submitCheck(url: string): Promise<CheckResponse> {
  const res = await fetch(`${API_BASE}/v1/check`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url }),
  });
  if (!res.ok) {
    let detail: unknown = null;
    try {
      detail = await res.json();
    } catch {
      detail = await res.text();
    }
    throw new ApiError(res.status, detail);
  }
  return (await res.json()) as CheckResponse;
}

/**
 * Server-side fetch of a saved report by id. Used by /check/[id] to render
 * the permanent, indexable view of a check. Returns null on 404 so the
 * page can call notFound() — every other error rethrows so Next.js
 * reports a 500.
 */
export async function getCheckById(id: string): Promise<CheckResponse | null> {
  const res = await fetch(`${API_BASE}/v1/checks/${encodeURIComponent(id)}`, {
    // ISR-friendly: re-fetch at most every 5 minutes. A check is mostly
    // immutable but the cache_hit / age display benefits from a periodic refresh.
    next: { revalidate: 300 },
  });
  if (res.status === 404) return null;
  if (!res.ok) {
    let detail: unknown = null;
    try {
      detail = await res.json();
    } catch {
      detail = await res.text();
    }
    throw new ApiError(res.status, detail);
  }
  return (await res.json()) as CheckResponse;
}

// ---------- Builder profile ----------

export interface BuilderRecentCheck {
  id: string;
  score: number | null;
  label: "safe" | "caution" | "risky" | null;
  title: string | null;
  price_inr: number | null;
  city: string | null;
  locality: string | null;
  portal: string;
  checked_at: string | null;
}

export interface BuilderReraRecord {
  state: string;
  rera_id: string;
  project_name: string | null;
  status: string | null;
}

export interface BuilderComplaintsByState {
  state: string;
  open: number;
  closed: number;
  delays: number;
}

export interface BuilderComplaints {
  open: number;
  closed: number;
  delays: number;
  by_state: BuilderComplaintsByState[];
}

export interface BuilderProfile {
  slug: string;
  name: string;
  aliases: string[];
  total_checks: number;
  avg_score: number | null;
  label_breakdown: { safe: number; caution: number; risky: number };
  cities: string[];
  states: string[];
  rera_records: BuilderReraRecord[];
  complaints: BuilderComplaints;
  recent_checks: BuilderRecentCheck[];
}

/**
 * Server-side fetch of the aggregated public builder profile. Used by
 * /builder/[slug] to render the permanent, indexable view. Returns null
 * on 404 so the page can call notFound(); other errors rethrow.
 */
export async function getBuilderBySlug(
  slug: string,
): Promise<BuilderProfile | null> {
  const res = await fetch(
    `${API_BASE}/v1/builders/${encodeURIComponent(slug)}`,
    { next: { revalidate: 300 } },
  );
  if (res.status === 404) return null;
  if (!res.ok) {
    let detail: unknown = null;
    try {
      detail = await res.json();
    } catch {
      detail = await res.text();
    }
    throw new ApiError(res.status, detail);
  }
  return (await res.json()) as BuilderProfile;
}

interface RecentBuildersResponse {
  items: Array<{ slug: string; checked_at: string | null }>;
  count: number;
}

/**
 * Recent builder slugs for sitemap generation. Tolerant of backend
 * failure — returns [] so sitemap.ts can still emit static pages.
 */
export async function getRecentBuilderSlugs(): Promise<
  RecentBuildersResponse["items"]
> {
  try {
    const res = await fetch(`${API_BASE}/v1/builders/recent?limit=500`, {
      next: { revalidate: 900 },
    });
    if (!res.ok) return [];
    const data = (await res.json()) as RecentBuildersResponse;
    return data.items ?? [];
  } catch {
    return [];
  }
}

export class ApiError extends Error {
  status: number;
  detail: unknown;
  constructor(status: number, detail: unknown) {
    super(`API error ${status}`);
    this.status = status;
    this.detail = detail;
  }
}

export function inrFormat(n?: number | null): string {
  if (n == null) return "—";
  if (n >= 10_000_000) return `₹${(n / 10_000_000).toFixed(2)} Cr`;
  if (n >= 100_000) return `₹${(n / 100_000).toFixed(2)} L`;
  return `₹${n.toLocaleString("en-IN")}`;
}
