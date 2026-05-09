import type { Metadata } from "next";
import Link from "next/link";

import { Footer } from "../../components/Footer";
import { Nav } from "../../components/Nav";

export const metadata: Metadata = {
  title: "About · PropCheck",
  description: "Why PropCheck exists, who built it, and where we're going.",
};

export default function AboutPage() {
  return (
    <main>
      <Nav />

      <section className="max-w-3xl mx-auto px-6 pt-20 pb-12">
        <div className="text-xs heading font-semibold uppercase tracking-wider text-ink/50 mb-4">About</div>
        <h1 className="heading text-5xl sm:text-6xl font-extrabold tracking-tight leading-[1.05] text-ink">
          Built for the<br/>moment before<br/>you pay a token.
        </h1>
        <p className="mt-8 text-lg text-ink/75 leading-relaxed">
          Every Indian who has bought or rented property in the last decade has the same story: a listing too good to be true, a broker who pressed for a quick token, a RERA number that didn&apos;t add up, photos that turned out to be from somewhere else. Lakhs lost, sometimes more. Always before any lawyer or bank got involved.
        </p>
        <p className="mt-4 text-lg text-ink/75 leading-relaxed">
          The portals can&apos;t fix this. They earn from every listing, real or fake. The buyer is on their own.
        </p>
        <p className="mt-4 text-lg text-ink/75 leading-relaxed">
          PropCheck is the neutral check that should have been there all along.
        </p>
      </section>

      <section className="max-w-3xl mx-auto px-6 pb-16">
        <h2 className="heading text-3xl font-bold text-ink mb-6">What we believe</h2>
        <div className="space-y-5 text-ink/85 leading-relaxed">
          <Belief n="01" title="Free for buyers, forever.">
            The person about to lose their savings is not the one who should pay for protection. Banks pay us to do the same check before disbursing a home loan. That subsidises the consumer side.
          </Belief>
          <Belief n="02" title="Evidence, never opinion.">
            Every red flag carries a citable source — Karnataka RERA, our locality price index, our perceptual-image database. If we get one wrong, you can flag the report and we review within 48 hours.
          </Belief>
          <Belief n="03" title="Neutral, by structure.">
            We are not a portal. We are not a broker. We have no commission. We have no listing inventory to defend. There is no scenario where it benefits us to mislead you.
          </Belief>
          <Belief n="04" title="Local, not generic.">
            Indian property fraud has its own grammar — RERA games, builder-delay patterns, broker price-shopping, stamp-duty workarounds. We&apos;re building for that grammar, one city at a time. Bangalore today, four more by end of year.
          </Belief>
        </div>
      </section>

      <section className="max-w-3xl mx-auto px-6 pb-16">
        <h2 className="heading text-3xl font-bold text-ink mb-6">Where we are</h2>
        <div className="bg-white border border-subtle rounded-2xl shadow-card p-6 space-y-3">
          <Row k="Live coverage" v="Bangalore (Karnataka RERA + 80 locality price benchmarks)" />
          <Row k="Surfaces" v="Web (live)" />
          <Row k="Coming next" v="Mumbai, Delhi NCR, Pune, Hyderabad — Q3-Q4 2026" />
          <Row k="Surfaces shipping next" v="Chrome extension + WhatsApp bot" />
        </div>
      </section>

      <section className="max-w-3xl mx-auto px-6 pb-20">
        <h2 className="heading text-3xl font-bold text-ink mb-6">How we make money</h2>
        <p className="text-ink/85 leading-relaxed">
          Banks and NBFCs spend ₹2,000&ndash;5,000 and 3&ndash;7 days on property due-diligence per loan file. We do the listing-fraud + RERA slice in under one second. Pilot is free; production is ₹50&ndash;200 per check, sliding by volume.
        </p>
        <p className="text-ink/85 leading-relaxed mt-3">
          That&apos;s it. We do not sell user data. We do not take broker commissions. We do not run ads. <Link href="/for-lenders" className="text-orange underline">More on the API →</Link>
        </p>
      </section>

      <section className="max-w-3xl mx-auto px-6 pb-12 text-center">
        <h2 className="heading text-3xl font-bold mb-4">Want in?</h2>
        <p className="text-ink/70 mb-6">Email us if you&apos;re a buyer, a builder, a bank, or a journalist with questions.</p>
        <a
          href="mailto:hello@propcheck.in"
          className="inline-block bg-orange hover:bg-orange-deep text-white heading font-semibold text-sm px-6 py-3 rounded-xl transition"
        >
          hello@propcheck.in →
        </a>
      </section>

      <Footer />
    </main>
  );
}

function Belief({ n, title, children }: { n: string; title: string; children: React.ReactNode }) {
  return (
    <div className="bg-white rounded-2xl border border-subtle shadow-card p-5">
      <div className="flex items-start gap-4">
        <div className="mono text-xs text-orange heading font-bold pt-1 shrink-0">{n}</div>
        <div>
          <div className="heading font-bold text-ink">{title}</div>
          <p className="text-sm text-ink/75 mt-2">{children}</p>
        </div>
      </div>
    </div>
  );
}

function Row({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-1 py-2 border-b border-subtle last:border-b-0">
      <div className="heading text-xs uppercase tracking-wider text-ink/50">{k}</div>
      <div className="text-sm text-ink/85">{v}</div>
    </div>
  );
}
