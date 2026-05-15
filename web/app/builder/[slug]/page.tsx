import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { Footer } from "../../../components/Footer";
import { Nav } from "../../../components/Nav";
import { getBuilderBySlug, inrFormat } from "../../../lib/api";
import type { BuilderProfile, BuilderRecentCheck } from "../../../lib/api";

/**
 * Permanent, indexable builder profile.
 *
 * Aggregates every check we've ever run against this builder + their
 * RERA registrations + open complaints into a single shareable URL.
 * Same compounding-SEO flywheel as /check/<id>: Google indexes
 * "Prestige Estates RERA complaints", buyers send the link to family
 * groups, journalists deep-link as evidence.
 */

const SITE = "https://propcheck.rohitraj.tech";

type Params = { params: { slug: string } };

export async function generateMetadata({ params }: Params): Promise<Metadata> {
  const profile = await getBuilderBySlug(params.slug).catch(() => null);
  if (!profile) {
    return {
      title: "Builder not found — PropCheck",
      description: "We don't have a profile for that builder yet.",
      robots: { index: false, follow: false },
    };
  }

  const where = profile.cities.slice(0, 3).join(", ") || "India";
  const breakdown = profile.label_breakdown;
  const totalFlagged = breakdown.caution + breakdown.risky;
  const verdict =
    profile.avg_score != null
      ? `Avg trust ${profile.avg_score}/100 across ${profile.total_checks} ${profile.total_checks === 1 ? "listing" : "listings"}`
      : `${profile.total_checks} ${profile.total_checks === 1 ? "listing" : "listings"} checked`;
  const title = `${profile.name} · ${verdict} · PropCheck`;
  const description = [
    `Independent trust profile for ${profile.name}${where ? ` (${where})` : ""}.`,
    `${breakdown.safe} safe, ${breakdown.caution} caution, ${breakdown.risky} risky.`,
    profile.complaints.open > 0
      ? `${profile.complaints.open} open RERA complaint${profile.complaints.open === 1 ? "" : "s"}.`
      : "",
    totalFlagged > 0
      ? "See exactly what's flagged before buying."
      : "",
  ]
    .filter(Boolean)
    .join(" ")
    .slice(0, 220);

  return {
    title,
    description,
    alternates: { canonical: `${SITE}/builder/${profile.slug}` },
    openGraph: {
      title,
      description,
      url: `${SITE}/builder/${profile.slug}`,
      type: "profile",
      siteName: "PropCheck",
    },
    twitter: { card: "summary", title, description },
    robots: { index: true, follow: true },
  };
}

export const revalidate = 300;

export default async function BuilderPage({ params }: Params) {
  const profile = await getBuilderBySlug(params.slug);
  if (!profile) {
    notFound();
  }

  return (
    <main>
      <Nav />
      <BuilderProfileView profile={profile} />
      <Footer />
    </main>
  );
}

function BuilderProfileView({ profile }: { profile: BuilderProfile }) {
  const { label_breakdown: bd, complaints } = profile;
  const totalForBar = Math.max(1, bd.safe + bd.caution + bd.risky);
  const safePct = Math.round((bd.safe / totalForBar) * 100);
  const cautionPct = Math.round((bd.caution / totalForBar) * 100);
  const riskyPct = Math.max(0, 100 - safePct - cautionPct);

  return (
    <section className="max-w-4xl mx-auto px-6 py-12 space-y-8">
      {/* Hero */}
      <header className="bg-white rounded-2xl shadow-card border border-subtle px-8 py-8">
        <div className="text-xs heading font-semibold text-orange uppercase tracking-wider">
          Builder profile
        </div>
        <h1 className="heading text-3xl sm:text-4xl font-extrabold text-ink mt-2 leading-tight">
          {profile.name}
        </h1>
        <div className="text-sm text-ink/70 mt-2">
          {profile.cities.length > 0 ? (
            <>Active in {profile.cities.join(", ")}.</>
          ) : (
            <>Locations not yet catalogued.</>
          )}
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mt-6">
          <Stat
            label="Listings checked"
            value={String(profile.total_checks)}
          />
          <Stat
            label="Avg trust score"
            value={profile.avg_score != null ? `${profile.avg_score} / 100` : "—"}
          />
          <Stat
            label="Open complaints"
            value={String(complaints.open)}
            warn={complaints.open > 0}
          />
          <Stat
            label="RERA records"
            value={String(profile.rera_records.length)}
          />
        </div>
      </header>

      {/* Score distribution */}
      <section className="bg-white rounded-2xl shadow-card border border-subtle px-8 py-6">
        <div className="text-xs text-ink/50 uppercase tracking-wider heading font-semibold">
          Trust score breakdown
        </div>
        <div className="mt-4 h-3 rounded-full overflow-hidden flex bg-subtle">
          {safePct > 0 && (
            <div
              className="bg-emerald-500"
              style={{ width: `${safePct}%` }}
              aria-label={`${bd.safe} safe`}
            />
          )}
          {cautionPct > 0 && (
            <div
              className="bg-amber-400"
              style={{ width: `${cautionPct}%` }}
              aria-label={`${bd.caution} caution`}
            />
          )}
          {riskyPct > 0 && (
            <div
              className="bg-red-500"
              style={{ width: `${riskyPct}%` }}
              aria-label={`${bd.risky} risky`}
            />
          )}
        </div>
        <div className="grid grid-cols-3 gap-2 mt-3 text-xs">
          <Legend swatch="bg-emerald-500" k="Safe" v={bd.safe} />
          <Legend swatch="bg-amber-400" k="Caution" v={bd.caution} />
          <Legend swatch="bg-red-500" k="Risky" v={bd.risky} />
        </div>
      </section>

      {/* Complaints */}
      {(complaints.open > 0 || complaints.closed > 0 || complaints.delays > 0) && (
        <section className="bg-white rounded-2xl shadow-card border border-subtle px-8 py-6">
          <div className="text-xs text-ink/50 uppercase tracking-wider heading font-semibold mb-4">
            RERA complaint history
          </div>
          <div className="grid grid-cols-3 gap-4 text-center">
            <ComplaintBucket label="Open" value={complaints.open} severity="high" />
            <ComplaintBucket label="Delays" value={complaints.delays} severity="medium" />
            <ComplaintBucket label="Closed" value={complaints.closed} severity="low" />
          </div>
          {complaints.by_state.length > 1 && (
            <div className="mt-5 text-xs text-ink/70 space-y-1">
              {complaints.by_state.map((b) => (
                <div key={b.state}>
                  <span className="font-semibold">{b.state}</span>: {b.open} open · {b.delays} delays · {b.closed} closed
                </div>
              ))}
            </div>
          )}
        </section>
      )}

      {/* RERA records */}
      {profile.rera_records.length > 0 && (
        <section className="bg-white rounded-2xl shadow-card border border-subtle px-8 py-6">
          <div className="text-xs text-ink/50 uppercase tracking-wider heading font-semibold mb-4">
            RERA registrations ({profile.rera_records.length})
          </div>
          <ul className="space-y-3">
            {profile.rera_records.map((r) => (
              <li
                key={`${r.state}-${r.rera_id}`}
                className="border border-subtle/70 rounded-xl p-3 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-1"
              >
                <div>
                  <div className="heading text-sm font-semibold text-ink">
                    {r.project_name ?? "(unnamed project)"}
                  </div>
                  <div className="mono text-xs text-ink/60 mt-0.5">{r.rera_id}</div>
                </div>
                <div className="text-xs text-ink/70 uppercase tracking-wider">
                  {r.state} · {r.status ?? "—"}
                </div>
              </li>
            ))}
          </ul>
        </section>
      )}

      {/* Recent checks */}
      {profile.recent_checks.length > 0 && (
        <section className="bg-white rounded-2xl shadow-card border border-subtle px-8 py-6">
          <div className="text-xs text-ink/50 uppercase tracking-wider heading font-semibold mb-4">
            Recent listings checked ({profile.recent_checks.length})
          </div>
          <ul className="divide-y divide-subtle/70">
            {profile.recent_checks.map((c) => (
              <li key={c.id} className="py-3">
                <RecentCheckRow check={c} />
              </li>
            ))}
          </ul>
        </section>
      )}

      {/* Disclaimer */}
      <section className="text-xs text-ink/60 leading-relaxed bg-cream rounded-2xl border border-subtle px-6 py-5">
        Data on this page is aggregated from public RERA portals and listings
        users have checked through PropCheck. Aliases observed for this builder:{" "}
        <span className="mono">
          {[profile.name, ...profile.aliases].slice(0, 6).join(" · ")}
        </span>
        . Trust scores are AI-driven signals, not legal advice — always verify
        title, sale deed and project status before paying anyone.
      </section>
    </section>
  );
}

function Stat({ label, value, warn }: { label: string; value: string; warn?: boolean }) {
  return (
    <div>
      <div className="text-xs text-ink/50 uppercase tracking-wider heading font-semibold">
        {label}
      </div>
      <div className={`mono text-2xl font-bold mt-1 ${warn ? "text-red-700" : "text-ink"}`}>
        {value}
      </div>
    </div>
  );
}

function Legend({ swatch, k, v }: { swatch: string; k: string; v: number }) {
  return (
    <div className="flex items-center gap-2">
      <span className={`inline-block w-3 h-3 rounded ${swatch}`} />
      <span className="text-ink/70">
        {k}: <span className="mono font-semibold text-ink">{v}</span>
      </span>
    </div>
  );
}

function ComplaintBucket({
  label,
  value,
  severity,
}: {
  label: string;
  value: number;
  severity: "high" | "medium" | "low";
}) {
  const colour =
    severity === "high"
      ? "text-red-700"
      : severity === "medium"
      ? "text-amber-700"
      : "text-emerald-700";
  return (
    <div className="border border-subtle/70 rounded-xl py-4">
      <div className={`mono text-3xl font-bold ${colour}`}>{value}</div>
      <div className="text-xs text-ink/60 uppercase tracking-wider heading font-semibold mt-1">
        {label}
      </div>
    </div>
  );
}

function RecentCheckRow({ check }: { check: BuilderRecentCheck }) {
  const labelColour =
    check.label === "safe"
      ? "text-emerald-700 bg-emerald-100"
      : check.label === "caution"
      ? "text-amber-700 bg-amber-100"
      : check.label === "risky"
      ? "text-red-700 bg-red-100"
      : "text-ink/70 bg-subtle";
  const where = [check.locality, check.city].filter(Boolean).join(", ") || "—";
  return (
    <Link
      href={`/check/${encodeURIComponent(check.id)}`}
      className="flex items-center justify-between gap-3 hover:bg-cream rounded-lg -mx-2 px-2 py-1 transition"
    >
      <div className="min-w-0">
        <div className="heading text-sm font-semibold text-ink truncate">
          {check.title ?? "Listing"}
        </div>
        <div className="text-xs text-ink/60 mt-0.5">
          {inrFormat(check.price_inr)} · {where} · {check.portal}
        </div>
      </div>
      <div className="flex items-center gap-3 shrink-0">
        {check.score != null && (
          <div className="mono text-lg font-bold text-ink">{check.score}</div>
        )}
        {check.label && (
          <span
            className={`text-[10px] heading font-bold ${labelColour} px-2 py-0.5 rounded uppercase tracking-wider`}
          >
            {check.label}
          </span>
        )}
      </div>
    </Link>
  );
}
