/**
 * 24h URL → CheckResponse cache, backed by chrome.storage.local.
 *
 * Key format: chk:<sha1(url).slice(0,16)>
 *   - sha1 keeps key length predictable regardless of URL length
 *   - 16 hex chars = 64 bits, plenty of headroom for our scale
 *   - "chk:" namespace prefix lets us prune our keys without touching others
 *
 * Lazy pruning runs on every setCached: anything older than 7d gets dropped.
 * No background timer — keeps the service worker idle.
 */

import type { CheckResponse } from "./types.js";

export const TTL_MS = 86_400_000; // 24h
const PRUNE_AFTER_MS = 7 * 86_400_000; // 7d
const KEY_PREFIX = "chk:";

interface CacheEntry {
  ts: number;
  url: string;
  report: CheckResponse;
}

async function sha1Hex(input: string): Promise<string> {
  const buf = new TextEncoder().encode(input);
  const digest = await crypto.subtle.digest("SHA-1", buf);
  const bytes = new Uint8Array(digest);
  let hex = "";
  for (let i = 0; i < bytes.length; i++) {
    hex += bytes[i].toString(16).padStart(2, "0");
  }
  return hex;
}

async function keyFor(url: string): Promise<string> {
  const hash = await sha1Hex(url);
  return KEY_PREFIX + hash.slice(0, 16);
}

function isCacheEntry(v: unknown): v is CacheEntry {
  return (
    !!v &&
    typeof v === "object" &&
    typeof (v as CacheEntry).ts === "number" &&
    typeof (v as CacheEntry).url === "string" &&
    !!(v as CacheEntry).report &&
    typeof (v as CacheEntry).report === "object"
  );
}

export async function getCached(url: string): Promise<CheckResponse | null> {
  if (!chrome?.storage?.local) return null;
  const key = await keyFor(url);
  const result = await chrome.storage.local.get(key);
  const entry = result[key];
  if (!isCacheEntry(entry)) return null;
  if (Date.now() - entry.ts > TTL_MS) return null;
  return entry.report;
}

export async function setCached(
  url: string,
  report: CheckResponse,
): Promise<void> {
  if (!chrome?.storage?.local) return;
  const key = await keyFor(url);
  const entry: CacheEntry = { ts: Date.now(), url, report };
  await chrome.storage.local.set({ [key]: entry });
  // Fire-and-forget prune; never block the caller.
  void pruneStale().catch(() => {});
}

async function pruneStale(): Promise<void> {
  const all = await chrome.storage.local.get(null);
  const now = Date.now();
  const toDrop: string[] = [];
  for (const [k, v] of Object.entries(all)) {
    if (!k.startsWith(KEY_PREFIX)) continue;
    if (!isCacheEntry(v)) {
      toDrop.push(k);
      continue;
    }
    if (now - v.ts > PRUNE_AFTER_MS) toDrop.push(k);
  }
  if (toDrop.length > 0) {
    await chrome.storage.local.remove(toDrop);
  }
}

/** Recent-checks ringbuffer for the popup. Capped at MAX entries. */
const RECENT_KEY = "recent_checks_v1";
const RECENT_MAX = 5;

export interface RecentCheck {
  ts: number;
  url: string;
  id: string;
  score: number;
  label: CheckResponse["label"];
  title: string | null;
}

export async function pushRecent(url: string, report: CheckResponse): Promise<void> {
  if (!chrome?.storage?.local) return;
  const result = await chrome.storage.local.get(RECENT_KEY);
  const list: RecentCheck[] = Array.isArray(result[RECENT_KEY])
    ? (result[RECENT_KEY] as RecentCheck[])
    : [];
  // Dedup by url — keep most recent.
  const filtered = list.filter((r) => r.url !== url);
  filtered.unshift({
    ts: Date.now(),
    url,
    id: report.id,
    score: report.score,
    label: report.label,
    title: report.property?.title ?? null,
  });
  const trimmed = filtered.slice(0, RECENT_MAX);
  await chrome.storage.local.set({ [RECENT_KEY]: trimmed });
}

export async function getRecent(): Promise<RecentCheck[]> {
  if (!chrome?.storage?.local) return [];
  const result = await chrome.storage.local.get(RECENT_KEY);
  return Array.isArray(result[RECENT_KEY]) ? (result[RECENT_KEY] as RecentCheck[]) : [];
}
