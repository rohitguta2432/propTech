import Link from "next/link";

import { Footer } from "../../../components/Footer";
import { Nav } from "../../../components/Nav";

export default function BuilderNotFound() {
  return (
    <main>
      <Nav />
      <section className="max-w-2xl mx-auto px-6 py-24 text-center">
        <div className="text-xs heading font-semibold text-orange uppercase tracking-wider">
          Builder not on file
        </div>
        <h1 className="heading text-4xl font-bold text-ink mt-3 leading-tight">
          We don&apos;t have a profile for that builder yet.
        </h1>
        <p className="text-ink/70 mt-4 leading-relaxed">
          Builder profiles are auto-generated from listings checked through
          PropCheck. Run a check on a listing by this developer and a profile
          will appear here within minutes.
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
