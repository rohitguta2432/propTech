/**
 * API client — mirrors web/lib/api.ts but adds extension-specific bits:
 *   - X-PropCheck-Surface: extension header for server-side surface logging
 *   - 429 handling that surfaces Retry-After through ApiError.retryAfter
 *   - AbortSignal support so callers can cancel in-flight requests on unmount
 */

import type { CheckResponse } from "./types.js";

export const API_BASE = "https://api.rohitraj.tech";

export class ApiError extends Error {
  status: number;
  detail: unknown;
  /** Seconds the client should wait before retrying. Populated on 429. */
  retryAfter?: number;
  constructor(status: number, detail: unknown, retryAfter?: number) {
    super(`API error ${status}`);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
    if (retryAfter !== undefined) this.retryAfter = retryAfter;
  }
}

export async function submitCheck(
  url: string,
  signal?: AbortSignal,
): Promise<CheckResponse> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}/v1/check`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-PropCheck-Surface": "extension",
      },
      body: JSON.stringify({ url }),
      signal,
    });
  } catch (e) {
    if (signal?.aborted) throw e;
    throw new ApiError(0, e instanceof Error ? e.message : String(e));
  }

  if (!res.ok) {
    let detail: unknown = null;
    try {
      detail = await res.json();
    } catch {
      try {
        detail = await res.text();
      } catch {
        detail = null;
      }
    }
    let retryAfter: number | undefined;
    if (res.status === 429) {
      const ra = res.headers.get("Retry-After");
      if (ra) {
        const parsed = Number.parseInt(ra, 10);
        if (Number.isFinite(parsed)) retryAfter = parsed;
      }
    }
    throw new ApiError(res.status, detail, retryAfter);
  }

  return (await res.json()) as CheckResponse;
}
