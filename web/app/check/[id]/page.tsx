import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { Footer } from "../../../components/Footer";
import { Nav } from "../../../components/Nav";
import { Report } from "../../../components/Report";
import { getCheckById, inrFormat } from "../../../lib/api";

/**
 * Permanent, indexable trust report page.
 *
 * Every saved check at `/v1/checks/<id>` gets its own URL here so:
 *   - Google can index "Prestige Lakeside RERA check" etc.
 *   - Buyers can share the report to WhatsApp / family groups with a
 *     proper link preview.
 *   - Press articles can deep-link to specific reports as evidence.
 *
 * Rendered server-side, ISR'd by the underlying fetch's `revalidate: 300`
 * in lib/api.ts so the public page stays fast and the listing-age line
 * stays roughly current.
 */

const SITE = "https://propcheck.rohitraj.tech";

type Params = { params: { id: string } };

export async function generateMetadata({ params }: Params): Promise<Metadata> {
  const report = await getCheckById(params.id).catch(() => null);
  if (!report) {
    return {
      title: "Report not found — PropCheck",
      description: "This trust report doesn't exist or has been removed.",
      robots: { index: false, follow: false },
    };
  }

  const p = report.property;
  const price = inrFormat(p.price_inr);
  const verdict =
    report.parse_confidence === "low"
      ? "Not enough data"
      : `Trust score ${report.score}/100 — ${report.label.toUpperCase()}`;
  const where = [p.locality, p.city].filter(Boolean).join(", ") || "India";
  const title = `${verdict} · ${p.bhk ?? ""}${p.bhk ? " BHK" : ""} in ${where} · PropCheck`;
  const description = [
    `${price} · ${p.title ?? "Property listing"} on ${p.portal}.`,
    report.summary,
    report.red_flags.length
      ? `${report.red_flags.length} red flag${report.red_flags.length === 1 ? "" : "s"} flagged.`
      : "",
  ]
    .filter(Boolean)
    .join(" ");

  return {
    title: title.replace(/\s+/g, " ").trim(),
    description: description.slice(0, 220),
    alternates: { canonical: `${SITE}/check/${report.id}` },
    openGraph: {
      title,
      description,
      url: `${SITE}/check/${report.id}`,
      type: "article",
      siteName: "PropCheck",
    },
    twitter: {
      card: "summary",
      title,
      description,
    },
    robots: { index: true, follow: true },
  };
}

export const revalidate = 300;

export default async function CheckPage({ params }: Params) {
  const report = await getCheckById(params.id);
  if (!report) {
    notFound();
  }

  return (
    <main>
      <Nav />
      <Report report={report} />
      <Footer />
    </main>
  );
}
