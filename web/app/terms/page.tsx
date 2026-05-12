import type { Metadata } from "next";
import Link from "next/link";

import { Footer } from "../../components/Footer";
import { Nav } from "../../components/Nav";

export const metadata: Metadata = {
  title: "Terms of Service · PropCheck",
  description: "Terms governing your use of PropCheck.",
};

export default function TermsPage() {
  return (
    <main>
      <Nav />
      <article className="max-w-3xl mx-auto px-6 pt-16 pb-12">
        <div className="text-xs heading font-semibold uppercase tracking-wider text-ink/50 mb-2">Legal</div>
        <h1 className="heading text-4xl font-extrabold text-ink leading-tight">Terms of Service</h1>
        <p className="text-ink/60 text-sm mt-2 italic">Effective 2026-05-09. By using PropCheck, you agree to these terms.</p>

        <Section title="What PropCheck is">
          <p className="text-ink/85 leading-relaxed">
            PropCheck is a free property-listing trust checker for India. Paste a listing URL, get a 0&ndash;100 Trust Score with explainable signals. We are not a property portal, broker, lawyer, or financial advisor.
          </p>
        </Section>

        <Section title="No warranty, no advice">
          <ul className="list-disc pl-5 space-y-2 text-ink/85">
            <li>Trust Scores are <strong>signals, not guarantees</strong>. A &quot;safe&quot; report does not mean the property is safe; a &quot;risky&quot; report does not mean it is fraudulent.</li>
            <li>Always verify in person, demand original documents, and consult a qualified lawyer before paying any token, advance, or full consideration.</li>
            <li>PropCheck is provided <strong>&quot;as is&quot;</strong> without warranties of accuracy, fitness for purpose, or availability.</li>
            <li>Nothing on PropCheck is investment, legal, or tax advice.</li>
          </ul>
        </Section>

        <Section title="Acceptable use">
          <p className="text-ink/85 mb-3">You agree NOT to:</p>
          <ul className="list-disc pl-5 space-y-2 text-ink/85">
            <li>Scrape, crawl, or hammer our service (over 10 requests/min/IP triggers automated rate limiting).</li>
            <li>Use PropCheck to harass any individual, broker, or builder identified in a report.</li>
            <li>Use PropCheck output to make false public claims about specific properties or sellers.</li>
            <li>Reverse-engineer, copy, or resell our API output without a B2B agreement.</li>
            <li>Use PropCheck for any purpose that violates Indian law.</li>
          </ul>
        </Section>

        <Section title="Intellectual property">
          <ul className="list-disc pl-5 space-y-2 text-ink/85">
            <li>The PropCheck product, name, design, code, and trust-engine signals are owned by us.</li>
            <li>You retain ownership of anything you submit (URLs, feedback). You grant us a non-exclusive licence to use it to operate and improve the service.</li>
            <li>Listings, photos, and RERA registry content belong to their respective owners. We display them under a fair-use understanding for verification purposes.</li>
          </ul>
        </Section>

        <Section title="Liability cap">
          <p className="text-ink/85 leading-relaxed">
            To the maximum extent permitted under Indian law, our total liability to you arising out of your use of PropCheck is limited to: (a) the amount you paid us in the 12 months prior to the claim, or (b) ₹1,000, whichever is greater. We are not liable for indirect, incidental, or consequential damages — including lost deposits, missed property purchases, or losses from acting on (or ignoring) a Trust Score.
          </p>
        </Section>

        <Section title="API users">
          <p className="text-ink/85 leading-relaxed mb-3">
            If you use the PropCheck API (B2B / Pro tiers, API keys starting with <code className="mono text-sm bg-subtle px-1 py-0.5 rounded">pk_*</code> or <code className="mono text-sm bg-subtle px-1 py-0.5 rounded">bk_*</code>), additional terms apply:
          </p>
          <ul className="list-disc pl-5 space-y-2 text-ink/85">
            <li>You will not share your API key, embed it in a public client, or redistribute the response payload.</li>
            <li>Caching of our responses is permitted up to 24 hours per (URL) tuple. Beyond that, re-fetch.</li>
            <li>Volume-based pricing is invoiced monthly. Disputes within 14 days; thereafter the invoice is deemed accepted.</li>
            <li>Either party may terminate with 30 days notice. We may suspend immediately on rate-limit abuse, ToS breach, or non-payment past 30 days.</li>
          </ul>
        </Section>

        <Section title="Termination">
          <p className="text-ink/85 leading-relaxed">
            You may stop using PropCheck at any time. We may suspend or terminate access for breach of these terms, abusive behaviour, or where required by law. Sections that should survive (Liability, IP, Indemnity, Governing law) survive termination.
          </p>
        </Section>

        <Section title="Indemnity">
          <p className="text-ink/85 leading-relaxed">
            You will indemnify PropCheck against third-party claims arising out of (a) your misuse of the service, (b) your violation of these terms, or (c) your reliance on a Trust Score against our explicit guidance.
          </p>
        </Section>

        <Section title="Governing law and jurisdiction">
          <p className="text-ink/85 leading-relaxed">
            These terms are governed by the laws of India. Disputes will be settled by the courts of <strong>Bangalore, Karnataka</strong>, except where a B2B agreement specifies otherwise.
          </p>
        </Section>

        <Section title="Changes to these terms">
          <p className="text-ink/85 leading-relaxed">
            We will date-stamp any change. Material changes (pricing, liability, scope) will be announced in the product 30 days before they take effect for B2B contracts; for free consumer use the new terms take effect on the date posted.
          </p>
        </Section>

        <Section title="Contact">
          <p className="text-ink/85 leading-relaxed">
            <a className="text-orange underline" href="mailto:rohitgupta2432@gmail.com">rohitgupta2432@gmail.com</a>.
          </p>
        </Section>

        <div className="mt-16 text-sm text-ink/60 italic border-t border-subtle pt-6">
          This document is a starting template. Before any commercial pilot or first B2B contract, have it reviewed by a lawyer qualified in Indian commercial and IT law.
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
