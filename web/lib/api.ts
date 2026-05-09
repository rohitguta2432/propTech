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

export interface Verifications {
  rera?: Record<string, unknown> | null;
  image_match_count?: number | null;
  locality_avg_price_per_sqft?: number | null;
  price_delta_pct?: number | null;
  listing_age_days?: number | null;
  builder_open_complaints?: number | null;
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
