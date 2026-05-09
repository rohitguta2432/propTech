import type { Metadata } from "next";
import Link from "next/link";

import { Footer } from "../../components/Footer";
import { Nav } from "../../components/Nav";

export const metadata: Metadata = {
  title: "How it works · PropCheck",
  description:
    "How PropCheck verifies an Indian property listing in 30 seconds — the 8 signals we check, where the data comes from, and how to read the Trust Score.",
};

export default function HowItWorksPage() {
  return (
    <main>
      <Nav />

      <Hero />
      <ThirtySecondFlow />
      <EightSignals />
      <ScoreBands />
      <DataSources />
      <Faq />
      <Cta />

      <Footer />
    </main>
  );
}

function Hero() {
  return (
    <section className="max-w-3xl mx-auto px-6 pt-20 pb-12 text-center">
      <div className="text-xs heading font-semibold uppercase tracking-wider text-ink/50 mb-4">
        How it works
      </div>
      <h1 className="heading text-5xl sm:text-6xl font-extrabold tracking-tight leading-[1.05] text-ink">
        Verify any listing in 30 seconds.
      </h1>
      <p className="mt-6 text-lg text-ink/70 leading-relaxed">
        Paste a property listing link. We pull the page, cross-check eight signals against public records and our own dataset, and hand back a 0&ndash;100 Trust Score with the exact reasons. Free for buyers. Forever.
      </p>
    </section>
  );
}

function ThirtySecondFlow() {
  const steps: { n: string; title: string; body: string }[] = [
    {
      n: "1",
      title: "Paste any link",
      body: "Magicbricks, 99acres, Housing.com or NoBroker. We accept the listing URL — you don't have to copy fields by hand.",
    },
    {
      n: "2",
      title: "We pull the listing",
      body: "Title, price, BHK, area, locality, RERA ID, builder. We cross-check all of it against Karnataka RERA, our locality price index, and our perceptual-image database.",
    },
    {
      n: "3",
      title: "Score in 30 seconds",
      body: "0–100 Trust Score with explainable red flags, green flags, and a pre-purchase checklist. No login required for the first five checks.",
    },
  ];
  return (
    <section className="max-w-5xl mx-auto px-6 pb-20">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {steps.map((s) => (
          <div key={s.n} className="bg-white rounded-2xl shadow-card border border-subtle p-6">
            <div className="mono text-3xl font-bold text-orange">{s.n}</div>
            <div className="heading text-lg font-bold text-ink mt-2">{s.title}</div>
            <p className="text-sm text-ink/70 mt-2 leading-relaxed">{s.body}</p>
          </div>
        ))}
      </div>
    </section>
  );
}

function EightSignals() {
  const signals: { code: string; title: string; body: string; severity: string }[] = [
    {
      code: "RERA_MATCH",
      title: "RERA verified",
      body: "Cross-check the RERA number on the listing against the state registry. Match → +10. Mismatch / not-found → -25.",
      severity: "positive",
    },
    {
      code: "RERA_MISSING",
      title: "RERA not provided",
      body: "Flats above ~800 sqft in Karnataka must register with RERA. No number on the listing → -10.",
      severity: "medium",
    },
    {
      code: "PRICE_BELOW_MARKET",
      title: "Price below market",
      body: "We compare ₹/sqft to the locality + BHK average from our 80-row Bangalore index. >15% below → bait or steal. -10.",
      severity: "medium",
    },
    {
      code: "PRICE_ABOVE_MARKET",
      title: "Price above market",
      body: ">25% above the locality average. Soft signal — could be premium, could be inflated. -5.",
      severity: "low",
    },
    {
      code: "LISTING_STALE",
      title: "Listing is stale",
      body: "Older than 180 days. Either nobody wants it or the broker re-lists weekly to look fresh. -5.",
      severity: "low",
    },
    {
      code: "DUPLICATE_LISTING",
      title: "Duplicate listings",
      body: "Same property listed across multiple portals at different prices. Different brokers, same flat — usually a games-the-broker-plays signal. -15 to -25.",
      severity: "high",
    },
    {
      code: "STOLEN_PHOTOS",
      title: "Photos likely stolen",
      body: "Perceptual hash (pHash) match against our image database. If listing photos appear on N other unrelated listings, treat with extreme caution. -25.",
      severity: "high",
    },
    {
      code: "BUILDER_COMPLAINTS",
      title: "Builder reputation",
      body: "Open RERA complaints + reported delays for the builder. 6+ open complaints → -10 to -20.",
      severity: "medium",
    },
  ];
  const pillFor = (s: string) =>
    s === "high"
      ? "text-red-700 bg-red-100"
      : s === "medium"
      ? "text-amber-700 bg-amber-100"
      : s === "positive"
      ? "text-emerald-700 bg-emerald-100"
      : "text-ink/60 bg-subtle";
  return (
    <section className="max-w-6xl mx-auto px-6 pb-20">
      <h2 className="heading text-3xl font-bold text-center mb-3">The eight signals</h2>
      <p className="text-center text-ink/70 max-w-2xl mx-auto mb-12 italic">
        Every flag has a public reason and a source. We never penalise without explaining why.
      </p>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {signals.map((s) => (
          <div key={s.code} className="bg-white rounded-2xl shadow-card border border-subtle p-5">
            <div className="flex items-start justify-between gap-3 mb-2">
              <div className="heading font-bold text-ink">{s.title}</div>
              <span className={`text-[10px] heading font-bold px-2 py-0.5 rounded uppercase ${pillFor(s.severity)}`}>
                {s.severity}
              </span>
            </div>
            <p className="text-sm text-ink/70 leading-relaxed">{s.body}</p>
            <div className="mono text-[10px] text-ink/50 mt-2">{s.code}</div>
          </div>
        ))}
      </div>
    </section>
  );
}

function ScoreBands() {
  return (
    <section className="max-w-5xl mx-auto px-6 pb-20">
      <h2 className="heading text-3xl font-bold text-center mb-12">Reading the Trust Score</h2>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <ScoreCard score={87} label="Safe" range="70–100" desc="Clean listing. RERA verified. Fair price. Visit with confidence and run our pre-purchase checklist." gradient="grad-safe" tone="emerald" />
        <ScoreCard score={62} label="Caution" range="40–69" desc="Mixed signals. Listing duplicated, or builder has minor complaints. Verify in person before paying any token." gradient="grad-amber" tone="amber" />
        <ScoreCard score={42} label="Risky" range="0–39" desc="High-risk signals. Stolen photos, fake RERA, suspicious price, or repeat-offender broker. Default position: walk away." gradient="grad-risky" tone="red" />
      </div>
    </section>
  );
}

function ScoreCard({
  score, label, range, desc, gradient, tone,
}: {
  score: number; label: string; range: string; desc: string; gradient: string; tone: "emerald" | "amber" | "red";
}) {
  const txt = tone === "emerald" ? "text-emerald-700" : tone === "amber" ? "text-amber-700" : "text-red-700";
  return (
    <div className="bg-white rounded-2xl shadow-card border border-subtle p-6">
      <div className={`${gradient} rounded-2xl p-6 flex flex-col items-center justify-center aspect-square`}>
        <div className={`mono text-7xl font-bold ${txt}`}>{score}</div>
        <div className={`mono text-xs ${txt} mt-1`}>/ 100</div>
        <div className={`mt-3 heading font-bold ${txt} tracking-wide text-sm`}>{label.toUpperCase()}</div>
      </div>
      <div className="heading font-semibold text-ink mt-4">Score {range}</div>
      <p className="text-sm text-ink/70 mt-1 leading-relaxed">{desc}</p>
    </div>
  );
}

function DataSources() {
  return (
    <section className="max-w-3xl mx-auto px-6 pb-20">
      <h2 className="heading text-3xl font-bold text-center mb-3">Where the data comes from</h2>
      <p className="text-center text-ink/70 mb-10 italic">
        Every claim cites a source. If we get one wrong, you can flag the report for review.
      </p>
      <div className="space-y-4">
        <Source title="Karnataka RERA registry" body="The state's official RERA portal — we cache project records for 7 days. Live verification of registration status, builder name, and project name." />
        <Source title="PropCheck locality price index" body="Curated ₹/sqft averages for 20 Bangalore localities × 4 BHK types. Refreshed monthly. Today's index covers 80 (locality, BHK) pairs in Bangalore; Mumbai, Delhi, Pune, Hyderabad expanding next." />
        <Source title="Perceptual image database" body="Every photo we've seen on a listing gets a 64-bit perceptual hash (pHash). Stolen-photo detection is just a Hamming-distance lookup against this database." />
        <Source title="Listing portals" body="Magicbricks, 99acres, Housing.com, NoBroker — we read the listing on submission, never crawl in bulk." />
      </div>
    </section>
  );
}

function Source({ title, body }: { title: string; body: string }) {
  return (
    <div className="bg-white rounded-xl border border-subtle p-5">
      <div className="heading font-semibold text-ink">{title}</div>
      <p className="text-sm text-ink/70 mt-1 leading-relaxed">{body}</p>
    </div>
  );
}

function Faq() {
  const items: { q: string; a: string }[] = [
    {
      q: "Is this really free?",
      a: "Yes. Forever, for buyers and renters. We charge banks and lenders for API access — that's how we keep the consumer side free and neutral.",
    },
    {
      q: "Will my listing search show up to brokers?",
      a: "No. We only fetch the page when you submit it. We don't share which listings you check with anyone — including the portals.",
    },
    {
      q: "Do you support cities outside Bangalore?",
      a: "RERA verification works across India once we add each state's registry; locality price benchmarks land city-by-city. Bangalore is live today; Mumbai, Delhi, Pune, Hyderabad next.",
    },
    {
      q: "What if you flag a listing wrongly?",
      a: "Every report has a 'Flag for review' link. We review reports manually within 48 hours and update the score if the signal was wrong.",
    },
    {
      q: "Do I need to create an account?",
      a: "Not for the first five checks. After that, free signup raises the limit to 30 checks per month. ₹499/year unlocks unlimited.",
    },
  ];
  return (
    <section className="max-w-3xl mx-auto px-6 pb-20">
      <h2 className="heading text-3xl font-bold text-center mb-10">FAQ</h2>
      <div className="space-y-3">
        {items.map((it) => (
          <details key={it.q} className="group bg-white border border-subtle rounded-xl p-5 cursor-pointer">
            <summary className="heading font-semibold text-ink list-none flex items-center justify-between">
              <span>{it.q}</span>
              <span className="text-ink/40 mono text-sm group-open:rotate-45 transition-transform">+</span>
            </summary>
            <p className="text-sm text-ink/70 mt-3 leading-relaxed">{it.a}</p>
          </details>
        ))}
      </div>
    </section>
  );
}

function Cta() {
  return (
    <section className="max-w-3xl mx-auto px-6 pb-12 text-center">
      <h2 className="heading text-3xl font-bold mb-4">Got a listing in mind?</h2>
      <p className="text-ink/70 mb-6">Paste it on the home page and see it scored in 30 seconds.</p>
      <Link
        href="/"
        className="inline-block bg-orange hover:bg-orange-deep text-white heading font-semibold text-sm px-6 py-3 rounded-xl transition"
      >
        Check a listing →
      </Link>
    </section>
  );
}
