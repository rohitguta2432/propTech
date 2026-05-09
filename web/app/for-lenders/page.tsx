import type { Metadata } from "next";
import Link from "next/link";

import { Footer } from "../../components/Footer";
import { Nav } from "../../components/Nav";

export const metadata: Metadata = {
  title: "For lenders · PropCheck API",
  description:
    "PropCheck API for banks and NBFCs — sub-second property listing fraud + RERA verification before home-loan disbursement. Bangalore live; multi-state expansion in progress.",
};

export default function ForLendersPage() {
  return (
    <main>
      <Nav />

      <Hero />
      <Problem />
      <Solution />
      <ApiPreview />
      <UseCases />
      <Pricing />
      <Coverage />
      <Cta />

      <Footer />
    </main>
  );
}

function Hero() {
  return (
    <section className="max-w-3xl mx-auto px-6 pt-20 pb-12 text-center">
      <div className="text-xs heading font-semibold uppercase tracking-wider text-orange mb-4">
        For lenders · API access
      </div>
      <h1 className="heading text-5xl sm:text-6xl font-extrabold tracking-tight leading-[1.05] text-ink">
        Cleaner home loan diligence,<br/>in one API call.
      </h1>
      <p className="mt-6 text-lg text-ink/70 leading-relaxed">
        Banks and NBFCs spend &#8377;2,000&ndash;5,000 and 3&ndash;7 days on property due-diligence per file.
        PropCheck does the listing-fraud and RERA slice in <strong className="text-ink">under one second</strong>, for a fraction of the cost.
      </p>
    </section>
  );
}

function Problem() {
  return (
    <section className="max-w-5xl mx-auto px-6 pb-20">
      <h2 className="heading text-3xl font-bold text-center mb-3">The hidden cost in every home loan</h2>
      <p className="text-center text-ink/70 max-w-2xl mx-auto mb-10 italic">
        Most retail lenders run property due-diligence in three siloed steps. Each one is slow, manual, and unreliable for the listing-fraud question.
      </p>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <Stat n="₹2K–5K" label="Per file" body="Field surveyor + legal vetting + valuation report. Rolled into the loan, ultimately paid by the borrower." />
        <Stat n="3–7 days" label="Turnaround" body="Surveyor visit, registry pulls, internal approvals. Disbursement waits on the slowest step." />
        <Stat n="65%" label="Buyers can't trust listings" body="Housing.com survey. Listing fraud isn't being checked at all in most lender workflows." />
      </div>
    </section>
  );
}

function Stat({ n, label, body }: { n: string; label: string; body: string }) {
  return (
    <div className="bg-white rounded-2xl shadow-card border border-subtle p-6">
      <div className="mono text-4xl font-bold text-orange">{n}</div>
      <div className="heading text-sm uppercase tracking-wider text-ink/60 mt-1">{label}</div>
      <p className="text-sm text-ink/70 mt-3 leading-relaxed">{body}</p>
    </div>
  );
}

function Solution() {
  return (
    <section className="max-w-3xl mx-auto px-6 pb-20">
      <h2 className="heading text-3xl font-bold text-center mb-3">One API call. Eight signals. Sub-second.</h2>
      <p className="text-center text-ink/70 leading-relaxed mb-10">
        Drop PropCheck into your loan-origination flow before disbursement. Each call returns a structured report with eight independent signals — each backed by a citable source.
      </p>
      <div className="bg-white border border-subtle rounded-2xl p-6 shadow-card">
        <ul className="space-y-3 text-sm">
          <Bullet>RERA registration cross-check (Karnataka live; multi-state in progress)</Bullet>
          <Bullet>Listing duplicates across portals — same property, different prices</Bullet>
          <Bullet>Photo theft detection via perceptual hashing</Bullet>
          <Bullet>Locality price benchmarking for unusual ₹/sqft</Bullet>
          <Bullet>Builder complaint + delay history from RERA registry</Bullet>
          <Bullet>Listing age + freshness</Bullet>
          <Bullet>Owner-name vs. property-tax record (where state APIs allow)</Bullet>
          <Bullet>Aggregated 0–100 Trust Score with explainable deltas</Bullet>
        </ul>
      </div>
    </section>
  );
}

function Bullet({ children }: { children: React.ReactNode }) {
  return (
    <li className="flex items-start gap-3">
      <span className="text-orange mt-0.5">✓</span>
      <span className="text-ink/85">{children}</span>
    </li>
  );
}

function ApiPreview() {
  const reqJson = `POST https://api.rohitraj.tech/v1/check
Content-Type: application/json
X-API-Key: bk_live_...

{
  "url": "https://www.magicbricks.com/propertyDetails/.../pdpid-..."
}`;
  const respJson = `{
  "id": "chk_a3f2c1d0",
  "score": 42,
  "label": "risky",
  "summary": "This listing has 4 high-risk signals.",
  "property": {
    "portal": "magicbricks",
    "rera_id": "PRM/KA/RERA/...",
    "builder_name": "ABC Developers",
    "price_inr": 12000000,
    "bhk": 3,
    "area_sqft": 1450,
    "locality": "Whitefield",
    "city": "Bangalore"
  },
  "red_flags": [
    { "code": "RERA_MISMATCH", "severity": "high", ... },
    { "code": "DUPLICATE_LISTING", "severity": "high", ... },
    { "code": "STOLEN_PHOTOS", "severity": "high", ... },
    { "code": "BUILDER_COMPLAINTS", "severity": "medium", ... }
  ],
  "verifications": {
    "rera": { "status": "MISMATCH" },
    "image_match_count": 7,
    "locality_avg_price_per_sqft": 10600,
    "price_delta_pct": -22,
    "builder_open_complaints": 6
  },
  "checked_at": "2026-05-09T11:30:00Z"
}`;
  return (
    <section className="max-w-5xl mx-auto px-6 pb-20">
      <h2 className="heading text-3xl font-bold text-center mb-12">API at a glance</h2>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div>
          <div className="text-xs heading font-bold uppercase tracking-wider text-ink/50 mb-2">Request</div>
          <pre className="bg-ink text-cream rounded-2xl p-5 overflow-x-auto text-xs leading-relaxed mono">
{reqJson}
          </pre>
        </div>
        <div>
          <div className="text-xs heading font-bold uppercase tracking-wider text-ink/50 mb-2">Response (excerpt)</div>
          <pre className="bg-ink text-cream rounded-2xl p-5 overflow-x-auto text-xs leading-relaxed mono">
{respJson}
          </pre>
        </div>
      </div>
      <p className="text-sm text-ink/60 text-center mt-6 italic">
        Full schema lives in the OpenAPI spec. SLA: P50 &lt; 200ms (cached), P99 &lt; 1s (cold). Idempotent on the URL — same input within 24h returns the cached report.
      </p>
    </section>
  );
}

function UseCases() {
  const cases: { title: string; body: string }[] = [
    {
      title: "Pre-disbursement check",
      body: "Run PropCheck after the borrower picks a property, before legal vetting starts. Stop bad files at the door — saves both legal and surveyor cost on listings that wouldn't pass anyway.",
    },
    {
      title: "Fraud screening",
      body: "Flag applications where the listed property doesn't match the registered RERA project, or where the broker has been linked to repeat-offender duplicate listings.",
    },
    {
      title: "Portfolio monitoring",
      body: "Re-run checks on existing collateral every quarter. Catch builder distress (rising complaint counts), price erosion in the locality, or RERA cancellations early.",
    },
    {
      title: "Borrower-facing verification",
      body: "Embed our /v1/check via your own UI as a 'Verify property' button on the borrower app. Demonstrates diligence to regulators and adds a trust touchpoint.",
    },
  ];
  return (
    <section className="max-w-5xl mx-auto px-6 pb-20">
      <h2 className="heading text-3xl font-bold text-center mb-12">Where it fits</h2>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {cases.map((c) => (
          <div key={c.title} className="bg-white rounded-2xl border border-subtle shadow-card p-6">
            <div className="heading font-bold text-ink">{c.title}</div>
            <p className="text-sm text-ink/70 mt-2 leading-relaxed">{c.body}</p>
          </div>
        ))}
      </div>
    </section>
  );
}

function Pricing() {
  const tiers: { name: string; price: string; sub: string; features: string[]; cta: string; highlight?: boolean }[] = [
    {
      name: "Pilot",
      price: "Free",
      sub: "First 1,000 checks",
      features: ["All 8 signals", "Full report JSON", "1-hour onboarding call", "Slack support"],
      cta: "Start a pilot",
    },
    {
      name: "Production",
      price: "₹50–200",
      sub: "per check, sliding by volume",
      features: ["All 8 signals", "P99 < 1s SLA", "Custom rate limits", "Email support", "Webhook delivery option"],
      cta: "Request pricing",
      highlight: true,
    },
    {
      name: "Annual",
      price: "Custom",
      sub: "Unlimited + dedicated support",
      features: ["Everything in Production", "Custom signals on your data", "Dedicated infra", "Quarterly reviews", "Compliance support"],
      cta: "Talk to us",
    },
  ];
  return (
    <section className="max-w-6xl mx-auto px-6 pb-20">
      <h2 className="heading text-3xl font-bold text-center mb-3">Pricing</h2>
      <p className="text-center text-ink/70 mb-12 italic">Free during pilot. Pay-per-check at production scale.</p>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {tiers.map((t) => (
          <div
            key={t.name}
            className={`rounded-2xl shadow-card p-6 ${t.highlight ? "bg-ink text-cream" : "bg-white border border-subtle"}`}
          >
            <div className={`heading text-xs font-bold uppercase tracking-wider ${t.highlight ? "text-orange" : "text-ink/50"}`}>
              {t.name}
            </div>
            <div className="mono text-4xl font-bold mt-3">{t.price}</div>
            <div className={`text-sm mt-1 ${t.highlight ? "text-cream/70" : "text-ink/60"}`}>{t.sub}</div>
            <ul className={`text-sm mt-5 space-y-2 ${t.highlight ? "text-cream/85" : "text-ink/85"}`}>
              {t.features.map((f) => <li key={f}>· {f}</li>)}
            </ul>
            <a
              href="mailto:hello@propcheck.in?subject=PropCheck%20API%20access"
              className={`mt-6 block text-center heading font-semibold text-sm px-4 py-2 rounded-xl transition ${
                t.highlight
                  ? "bg-orange hover:bg-orange-deep text-white"
                  : "border border-ink/20 hover:border-ink text-ink"
              }`}
            >
              {t.cta} →
            </a>
          </div>
        ))}
      </div>
    </section>
  );
}

function Coverage() {
  return (
    <section className="max-w-3xl mx-auto px-6 pb-20">
      <h2 className="heading text-3xl font-bold text-center mb-3">Coverage</h2>
      <p className="text-center text-ink/70 leading-relaxed mb-10">
        Bangalore is live today. We add states city-by-city — RERA registry first, locality price index second.
      </p>
      <div className="bg-white border border-subtle rounded-2xl shadow-card p-6">
        <CoverageRow city="Bangalore" rera="✅ Karnataka RERA" prices="✅ 80 (locality × BHK) pairs" />
        <CoverageRow city="Mumbai" rera="🚧 MahaRERA — Q3 2026" prices="🚧 Q3 2026" />
        <CoverageRow city="Delhi NCR" rera="🚧 RERA Delhi + UP-RERA + HARERA — Q4 2026" prices="🚧 Q4 2026" />
        <CoverageRow city="Pune" rera="🚧 MahaRERA — Q3 2026" prices="🚧 Q3 2026" />
        <CoverageRow city="Hyderabad" rera="🚧 TS-RERA — Q4 2026" prices="🚧 Q4 2026" />
      </div>
      <p className="text-xs text-ink/50 italic mt-4 text-center">
        Pilot partners get priority on next-city rollout.
      </p>
    </section>
  );
}

function CoverageRow({ city, rera, prices }: { city: string; rera: string; prices: string }) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-3 py-3 border-b border-subtle last:border-b-0">
      <div className="heading font-semibold text-ink">{city}</div>
      <div className="text-sm text-ink/70">{rera}</div>
      <div className="text-sm text-ink/70">{prices}</div>
    </div>
  );
}

function Cta() {
  return (
    <section className="max-w-3xl mx-auto px-6 pb-12 text-center">
      <h2 className="heading text-3xl font-bold mb-4">Start a pilot</h2>
      <p className="text-ink/70 mb-6">First 1,000 checks free. One-hour onboarding. Slack support.</p>
      <a
        href="mailto:hello@propcheck.in?subject=PropCheck%20API%20pilot&body=Hi%20%E2%80%94%20I%27d%20like%20to%20pilot%20PropCheck.%20Volume%20expectation%3A%20%5B%5D%20checks%2Fmonth.%20Use%20case%3A%20%5B%5D."
        className="inline-block bg-orange hover:bg-orange-deep text-white heading font-semibold text-sm px-6 py-3 rounded-xl transition"
      >
        Email hello@propcheck.in →
      </a>
      <p className="mt-6 text-xs text-ink/50">
        We respond within one business day. Or hit{" "}
        <Link href="/" className="underline">propcheck.rohitraj.tech</Link>{" "}
        first to see a live report.
      </p>
    </section>
  );
}
