import Link from "next/link";

import { Footer } from "../../../components/Footer";
import { Nav } from "../../../components/Nav";

export default function CheckNotFound() {
  return (
    <main>
      <Nav />
      <section className="max-w-2xl mx-auto px-6 py-24 text-center">
        <div className="text-xs heading font-semibold text-orange uppercase tracking-wider">
          Report not found
        </div>
        <h1 className="heading text-4xl font-bold text-ink mt-3 leading-tight">
          We couldn&apos;t find that trust report.
        </h1>
        <p className="text-ink/70 mt-4 leading-relaxed">
          It may have been removed, or the link may be wrong. You can run a fresh check
          on the home page — pastes a listing URL and you get a new report in 30 seconds.
        </p>
        <Link
          href="/"
          className="inline-block mt-8 bg-orange hover:bg-orange-deep text-white heading font-semibold text-sm px-6 py-3 rounded-xl transition"
        >
          Run a new check →
        </Link>
      </section>
      <Footer />
    </main>
  );
}
