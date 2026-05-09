import Link from "next/link";

import { Footer } from "../components/Footer";
import { Nav } from "../components/Nav";

export const metadata = {
  title: "Page not found · PropCheck",
};

export default function NotFound() {
  return (
    <main>
      <Nav />
      <section className="max-w-2xl mx-auto px-6 pt-32 pb-20 text-center">
        <div className="mono text-7xl font-bold text-orange">404</div>
        <h1 className="heading text-3xl font-bold text-ink mt-4">This page is missing.</h1>
        <p className="text-ink/70 mt-4 leading-relaxed">
          Like a property listing with no RERA number, this URL doesn&apos;t check out.
          Try the home page or one of the working sections.
        </p>
        <div className="mt-8 flex flex-col sm:flex-row gap-3 justify-center">
          <Link href="/" className="bg-orange hover:bg-orange-deep text-white heading font-semibold text-sm px-5 py-2.5 rounded-xl transition">
            Home
          </Link>
          <Link href="/how-it-works" className="border border-subtle hover:bg-white text-ink heading font-medium text-sm px-5 py-2.5 rounded-xl transition">
            How it works
          </Link>
          <Link href="/for-lenders" className="border border-subtle hover:bg-white text-ink heading font-medium text-sm px-5 py-2.5 rounded-xl transition">
            For lenders
          </Link>
        </div>
      </section>
      <Footer />
    </main>
  );
}
