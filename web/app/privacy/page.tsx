import type { Metadata } from "next";
import Link from "next/link";

import { Footer } from "../../components/Footer";
import { Nav } from "../../components/Nav";

export const metadata: Metadata = {
  title: "Privacy Policy · PropCheck",
  description: "How PropCheck collects, uses, and protects your data.",
};

export default function PrivacyPage() {
  return (
    <main>
      <Nav />
      <article className="max-w-3xl mx-auto px-6 pt-16 pb-12">
        <div className="text-xs heading font-semibold uppercase tracking-wider text-ink/50 mb-2">Legal</div>
        <h1 className="heading text-4xl font-extrabold text-ink leading-tight">Privacy Policy</h1>
        <p className="text-ink/60 text-sm mt-2 italic">Effective 2026-05-09. We may update this; the version date above is what applies on the day you used the service.</p>

        <Section title="What we collect">
          <ul className="list-disc pl-5 space-y-2 text-ink/85">
            <li><strong>Listing URLs you submit.</strong> Stored in our database alongside the report we generated.</li>
            <li><strong>Your IP address.</strong> For rate-limiting and abuse prevention only. Truncated to /24 for analytics.</li>
            <li><strong>Your user-agent string.</strong> So we know which surface (web, extension, WhatsApp) the request came from.</li>
            <li><strong>Optional email</strong> if you submit feedback through `/v1/feedback`.</li>
            <li><strong>Public listing data we scrape</strong> — title, price, BHK, photos, RERA ID, builder. This is data you could see on the listing yourself.</li>
            <li><strong>Public RERA registry data</strong> — verification status of RERA IDs against the relevant state portal.</li>
          </ul>
        </Section>

        <Section title="What we do NOT collect">
          <ul className="list-disc pl-5 space-y-2 text-ink/85">
            <li>Your name, phone number, address, Aadhaar, PAN, or any government ID. We do not ask, you do not give.</li>
            <li>Your bank, card, UPI, or any payment information at MVP.</li>
            <li>Browser history, cookies, or fingerprints from outside our domain.</li>
            <li>The content of pages you visit when you are not on PropCheck.</li>
          </ul>
        </Section>

        <Section title="How we use it">
          <ul className="list-disc pl-5 space-y-2 text-ink/85">
            <li>To compute and return your Trust Score.</li>
            <li>To cache reports for 24 hours so a re-check is instant.</li>
            <li>To improve our scam-detection signals (aggregated, anonymous patterns only).</li>
            <li>To debug errors and prevent abuse.</li>
            <li>If you are a B2B / Pro API user, to bill you per-check.</li>
          </ul>
        </Section>

        <Section title="What we share">
          <ul className="list-disc pl-5 space-y-2 text-ink/85">
            <li><strong>Nothing</strong> with brokers, listing portals, or marketers. We do not sell or rent any data.</li>
            <li>Aggregated, anonymous statistics with banks who pay for our API (e.g. &quot;listing-fraud incidence in Whitefield this quarter&quot;).</li>
            <li>Information required by lawful court or regulatory order, after we&apos;ve evaluated whether we can lawfully refuse.</li>
            <li>Service providers we use under data-processing agreements: Supabase (database, Singapore region), Vercel (hosting, EU+US edge).</li>
          </ul>
        </Section>

        <Section title="Cookies">
          <p className="text-ink/85 leading-relaxed">
            At MVP we set <strong>no cookies</strong> on the consumer site. If we add analytics later (PostHog or Plausible), we will use cookieless analytics where possible and update this policy before turning anything on.
          </p>
        </Section>

        <Section title="Your rights">
          <p className="text-ink/85 leading-relaxed mb-3">
            Email <a className="text-orange underline" href="mailto:hello@propcheck.in">hello@propcheck.in</a> to:
          </p>
          <ul className="list-disc pl-5 space-y-2 text-ink/85">
            <li>Request a copy of any data we hold tied to your IP, email, or submitted URL.</li>
            <li>Request deletion of any record you can identify.</li>
            <li>Object to processing — we will stop unless we have a legal basis to continue.</li>
          </ul>
          <p className="text-ink/85 mt-3">We respond within 30 days.</p>
        </Section>

        <Section title="Retention">
          <p className="text-ink/85 leading-relaxed">
            Check reports: 12 months, then archived. IP-bound rate-limit counters: 1 hour. Server logs: 30 days. Listing snapshots: indefinite (this is the data moat). Feedback you submit: indefinite.
          </p>
        </Section>

        <Section title="Children">
          <p className="text-ink/85 leading-relaxed">
            PropCheck is not intended for users under 18. We do not knowingly collect data from minors.
          </p>
        </Section>

        <Section title="Changes">
          <p className="text-ink/85 leading-relaxed">
            We will date-stamp any change to this page. Material changes (more data collected, new sharing) will be announced in the product before they take effect.
          </p>
        </Section>

        <Section title="Contact">
          <p className="text-ink/85 leading-relaxed">
            <a className="text-orange underline" href="mailto:hello@propcheck.in">hello@propcheck.in</a>. Bangalore, India.
          </p>
        </Section>

        <div className="mt-16 text-sm text-ink/60 italic border-t border-subtle pt-6">
          This document is a starting template. Before any commercial pilot with a regulated entity (bank, NBFC, broker), have it reviewed by a lawyer qualified in Indian data-protection law (esp. the Digital Personal Data Protection Act, 2023).
        </div>

        <div className="mt-8">
          <Link href="/" className="text-orange heading text-sm">← Back to home</Link>
        </div>
      </article>
      <Footer />
    </main>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="mt-10">
      <h2 className="heading text-xl font-bold text-ink mb-3">{title}</h2>
      <div className="leading-relaxed">{children}</div>
    </section>
  );
}
