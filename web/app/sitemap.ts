import type { MetadataRoute } from "next";

import { API_BASE, getRecentBuilderSlugs } from "../lib/api";

const SITE = "https://propcheck.rohitraj.tech";

/**
 * Next.js regenerates sitemap.xml at most this often (in seconds).
 * Keeping it ~15 min means newly-run checks land in Google's discovery
 * queue quickly without hammering the backend.
 */
export const revalidate = 900;

interface RecentChecksResponse {
  items: Array<{ id: string; checked_at: string | null }>;
  count: number;
}

async function fetchRecentCheckIds(): Promise<RecentChecksResponse["items"]> {
  try {
    const res = await fetch(`${API_BASE}/v1/checks/recent?limit=500`, {
      next: { revalidate: 900 },
    });
    if (!res.ok) return [];
    const data = (await res.json()) as RecentChecksResponse;
    return data.items ?? [];
  } catch {
    // Sitemap must never crash the build; static pages are still emitted.
    return [];
  }
}

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const now = new Date();
  const staticPages: MetadataRoute.Sitemap = [
    { url: `${SITE}/`, lastModified: now, changeFrequency: "weekly", priority: 1.0 },
    { url: `${SITE}/how-it-works`, lastModified: now, changeFrequency: "monthly", priority: 0.8 },
    { url: `${SITE}/for-lenders`, lastModified: now, changeFrequency: "monthly", priority: 0.8 },
    { url: `${SITE}/about`, lastModified: now, changeFrequency: "monthly", priority: 0.5 },
    { url: `${SITE}/privacy`, lastModified: now, changeFrequency: "yearly", priority: 0.3 },
    { url: `${SITE}/terms`, lastModified: now, changeFrequency: "yearly", priority: 0.3 },
  ];

  const [recent, recentBuilders] = await Promise.all([
    fetchRecentCheckIds(),
    getRecentBuilderSlugs(),
  ]);
  const reportPages: MetadataRoute.Sitemap = recent.map((c) => ({
    url: `${SITE}/check/${encodeURIComponent(c.id)}`,
    lastModified: c.checked_at ? new Date(c.checked_at) : now,
    changeFrequency: "monthly",
    priority: 0.6,
  }));
  const builderPages: MetadataRoute.Sitemap = recentBuilders.map((b) => ({
    url: `${SITE}/builder/${encodeURIComponent(b.slug)}`,
    lastModified: b.checked_at ? new Date(b.checked_at) : now,
    changeFrequency: "weekly",
    priority: 0.7,
  }));

  return [...staticPages, ...reportPages, ...builderPages];
}
