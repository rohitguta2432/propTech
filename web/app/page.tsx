"use client";

import { useState } from "react";

import { Footer } from "../components/Footer";
import { Nav } from "../components/Nav";
import { Report } from "../components/Report";
import { ApiError, CheckResponse, submitCheck } from "../lib/api";

export default function HomePage() {
  const [url, setUrl] = useState("");
  const [report, setReport] = useState<CheckResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setReport(null);
    setLoading(true);
    try {
      const r = await submitCheck(url.trim());
      setReport(r);
      // Smooth scroll to report
      setTimeout(() => {
        document.getElementById("report")?.scrollIntoView({ behavior: "smooth" });
      }, 50);
    } catch (e) {
      if (e instanceof ApiError) {
        const d = e.detail as { detail?: { message?: string } } | null;
        setError(d?.detail?.message ?? `Error ${e.status}`);
      } else {
        setError("Network error — backend unreachable.");
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <main>
      <Nav />
      <Hero url={url} setUrl={setUrl} onSubmit={onSubmit} loading={loading} error={error} />
      {report && <Report report={report} />}
      <HowItWorks />
      <Footer />
    </main>
  );
}

function Hero({
  url,
  setUrl,
  onSubmit,
  loading,
  error,
}: {
  url: string;
  setUrl: (s: string) => void;
  onSubmit: (e: React.FormEvent) => void;
  loading: boolean;
  error: string | null;
}) {
  return (
    <section className="max-w-4xl mx-auto px-6 pt-20 pb-12 text-center">
      <div className="inline-flex items-center gap-2 bg-white border border-subtle rounded-full px-3 py-1 text-xs heading font-medium mb-6">
        <span className="w-1.5 h-1.5 rounded-full bg-orange animate-pulse"></span>
        <span className="text-ink/70">Bangalore launch · May 2026</span>
      </div>
      <h1 className="heading text-5xl sm:text-6xl font-extrabold tracking-tight leading-[1.05] text-ink">
        Don&apos;t get scammed on<br/>your next property.
      </h1>
      <p className="mt-6 text-lg text-ink/70 max-w-2xl mx-auto leading-relaxed">
        AI-powered trust score for any Magicbricks, 99acres, Housing or NoBroker listing in 30 seconds.
        Free. Neutral. Built for Indian buyers.
      </p>

      <form onSubmit={onSubmit} className="mt-10 max-w-xl mx-auto">
        <div className="flex flex-col sm:flex-row gap-2 p-2 bg-white rounded-2xl shadow-card border border-subtle">
          <input
            type="text"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="Paste a property listing link…"
            className="flex-1 px-3 py-2 text-sm bg-transparent outline-none font-body"
            required
          />
          <button
            type="submit"
            disabled={loading || !url.trim()}
            className="bg-orange hover:bg-orange-deep disabled:bg-midgray text-white heading font-semibold text-sm px-5 py-2 rounded-xl transition"
          >
            {loading ? "Checking…" : "Check →"}
          </button>
        </div>
        {error && (
          <p className="mt-3 text-sm text-risky">{error}</p>
        )}
        {!error && (
          <p className="mt-3 text-xs text-ink/60">
            Free forever for buyers. We don&apos;t sell listings. We don&apos;t take broker commissions.
          </p>
        )}
      </form>
    </section>
  );
}

function HowItWorks() {
  return (
    <section className="max-w-5xl mx-auto px-6 py-20">
      <h2 className="heading text-3xl font-bold text-center mb-12">How our AI works</h2>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <Step n="1" title="Paste any link" body="Magicbricks, 99acres, Housing or NoBroker. Our AI reads the listing — you don't have to copy anything." />
        <Step n="2" title="AI checks 8 signals" body="Listing age. Price vs locality. Duplicate count. RERA registration. Image reverse-search. Builder complaints. Owner-name match. Suspicious patterns." />
        <Step n="3" title="30-second Trust Score" body="0–100 AI-driven score. Clear red flags. A checklist of what to verify before paying anyone." />
      </div>
    </section>
  );
}

function Step({ n, title, body }: { n: string; title: string; body: string }) {
  return (
    <div className="bg-white rounded-2xl shadow-card border border-subtle p-6">
      <div className="mono text-3xl font-bold text-orange">{n}</div>
      <div className="heading text-lg font-bold text-ink mt-2">{title}</div>
      <p className="text-sm text-ink/70 mt-2 leading-relaxed">{body}</p>
    </div>
  );
}

