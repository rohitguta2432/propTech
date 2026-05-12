import type { CheckResponse, Flag } from "../lib/api";
import { inrFormat } from "../lib/api";

/**
 * Full trust report card — used on the home page after a fresh check
 * AND on the permanent /check/[id] route. Pure: no state, no fetching,
 * safe to render server-side.
 *
 * The component honors `report.parse_confidence`: when "low" it
 * replaces the misleading "50 / CAUTION" score banner with a
 * "Not enough data" treatment. The trust engine emits a neutral
 * placeholder score for low-confidence parses; we must not render
 * that as if it were a real verdict.
 */
export function Report({ report }: { report: CheckResponse }) {
  const isLowConfidence = report.parse_confidence === "low";
  const grad = isLowConfidence
    ? "bg-cream"
    : report.label === "safe"
    ? "grad-safe"
    : report.label === "caution"
    ? "grad-amber"
    : "grad-risky";
  const txt = isLowConfidence
    ? "text-ink/70"
    : report.label === "safe"
    ? "text-emerald-700"
    : report.label === "caution"
    ? "text-amber-700"
    : "text-red-700";

  return (
    <section id="report" className="max-w-4xl mx-auto px-6 py-12">
      <div className="bg-white rounded-2xl shadow-card border border-subtle overflow-hidden">
        {/* Score banner */}
        <div className={`${grad} px-8 py-10 flex flex-col md:flex-row items-center gap-8`}>
          <div className="rounded-2xl px-8 py-6 flex flex-col items-center justify-center min-w-[180px] bg-white/70 backdrop-blur">
            {isLowConfidence ? (
              <>
                <div className={`heading text-3xl font-bold ${txt} text-center leading-tight`}>
                  Not enough data
                </div>
                <div className={`mono text-[11px] ${txt} mt-3 tracking-wide`}>
                  COULDN&apos;T SCORE
                </div>
              </>
            ) : (
              <>
                <div className={`mono text-7xl font-bold ${txt}`}>{report.score}</div>
                <div className={`mono text-xs ${txt}`}>/ 100</div>
                <div className={`mt-3 heading font-bold ${txt} tracking-wide text-sm`}>
                  {report.label.toUpperCase()}
                </div>
              </>
            )}
          </div>
          <div className="flex-1 text-center md:text-left">
            <div className="heading text-2xl font-bold text-ink">{report.summary}</div>
            <div className="text-ink/80 mt-2 text-sm">
              {report.cache_hit ? "Cached report (under 24h old)." : "Fresh report."}
              {" "}Checked at {new Date(report.checked_at).toLocaleString()}.
            </div>
          </div>
        </div>

        {/* Property */}
        <div className="px-8 py-6 border-b border-subtle">
          <div className="text-xs text-ink/50 uppercase tracking-wider heading font-semibold">Property</div>
          <div className="mt-2 heading text-xl font-bold text-ink">
            {report.property.title ?? "—"}
          </div>
          <div className="mt-1 text-sm text-ink/70">
            <span className="mono font-semibold">{inrFormat(report.property.price_inr)}</span>
            {report.property.area_sqft && (
              <> · <span className="mono">{report.property.area_sqft} sqft</span></>
            )}
            {report.property.bhk && (
              <> · <span className="mono">{report.property.bhk} BHK</span></>
            )}
          </div>
          <div className="mt-2 text-xs text-ink/60">
            Source: {report.property.portal} · Listing ID {report.property.listing_id}
          </div>
        </div>

        {/* Red flags */}
        {report.red_flags.length > 0 && (
          <div className="px-8 py-6 border-b border-subtle">
            <div className="text-xs text-ink/50 uppercase tracking-wider heading font-semibold mb-4">
              Red Flags ({report.red_flags.length})
            </div>
            <div className="space-y-3">
              {report.red_flags.map((f) => <FlagCard key={f.code} flag={f} />)}
            </div>
          </div>
        )}

        {/* Green flags */}
        {report.green_flags.length > 0 && (
          <div className="px-8 py-6 border-b border-subtle">
            <div className="text-xs text-ink/50 uppercase tracking-wider heading font-semibold mb-4">
              Green Flags ({report.green_flags.length})
            </div>
            <div className="space-y-3">
              {report.green_flags.map((f) => <FlagCard key={f.code} flag={f} />)}
            </div>
          </div>
        )}

        {/* Checklist */}
        <div className="px-8 py-6 border-b border-subtle">
          <div className="text-xs text-ink/50 uppercase tracking-wider heading font-semibold mb-4">
            Pre-Purchase Checklist
          </div>
          <ul className="space-y-2 text-sm">
            {report.checklist.map((item, i) => (
              <li key={i} className="flex items-start gap-2">
                <input type="checkbox" className="mt-0.5 w-4 h-4 rounded border-subtle accent-orange" />
                <span className="text-ink/85">{item}</span>
              </li>
            ))}
          </ul>
        </div>

        {/* Verifications */}
        <div className="px-8 py-6 bg-cream">
          <div className="text-xs text-ink/50 uppercase tracking-wider heading font-semibold mb-3">
            Verification details
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-sm">
            <Row k="RERA status" v={report.verifications.rera ? JSON.stringify((report.verifications.rera as { status?: string }).status ?? "—") : "—"} />
            <Row k="Listing age" v={report.verifications.listing_age_days != null ? `${report.verifications.listing_age_days} days` : "—"} />
            <Row k="Locality avg ₹/sqft" v={report.verifications.locality_avg_price_per_sqft != null ? `₹${report.verifications.locality_avg_price_per_sqft.toLocaleString("en-IN")}` : "—"} />
            <Row k="Image matches" v={report.verifications.image_match_count != null ? `${report.verifications.image_match_count}` : "—"} />
            <Row k="Builder complaints" v={report.verifications.builder_open_complaints != null ? `${report.verifications.builder_open_complaints}` : "—"} />
            <Row k="Report id" v={report.id} mono />
          </div>
        </div>
      </div>
    </section>
  );
}

function Row({ k, v, mono }: { k: string; v: string; mono?: boolean }) {
  return (
    <div className="flex justify-between gap-2 border-b border-subtle/50 py-1.5">
      <span className="text-ink/70">{k}</span>
      <span className={`text-ink ${mono ? "mono" : ""}`}>{v}</span>
    </div>
  );
}

function FlagCard({ flag }: { flag: Flag }) {
  const wrap =
    flag.severity === "high"
      ? "border-red-200 bg-red-50/60"
      : flag.severity === "medium"
      ? "border-amber-200 bg-amber-50/60"
      : flag.severity === "positive"
      ? "border-emerald-200 bg-emerald-50/60"
      : "border-subtle bg-cream";
  const pill =
    flag.severity === "high"
      ? "text-red-700 bg-red-100"
      : flag.severity === "medium"
      ? "text-amber-700 bg-amber-100"
      : flag.severity === "positive"
      ? "text-emerald-700 bg-emerald-100"
      : "text-ink/70 bg-subtle";

  return (
    <div className={`border ${wrap} rounded-xl p-4 flex gap-3`}>
      <div className="text-lg leading-none mt-0.5">{flag.severity === "positive" ? "✓" : "⚠"}</div>
      <div className="flex-1">
        <div className="flex items-center justify-between gap-2">
          <div className="heading font-semibold text-ink text-sm sm:text-base">{flag.label}</div>
          <span className={`text-xs heading font-bold ${pill} px-2 py-0.5 rounded uppercase`}>
            {flag.severity}
          </span>
        </div>
        <div className="text-sm text-ink/80 mt-1 leading-relaxed">{flag.description}</div>
        <div className="text-xs text-ink/60 mt-2">Source: {flag.source}</div>
      </div>
    </div>
  );
}
