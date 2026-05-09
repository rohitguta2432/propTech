import Link from "next/link";

export function Footer() {
  return (
    <footer className="border-t border-subtle py-10 mt-20">
      <div className="max-w-6xl mx-auto px-6 flex flex-col md:flex-row gap-6 items-center justify-between text-sm text-ink/60">
        <div className="font-body text-center md:text-left">
          PropCheck · 2026 · Made in Bangalore for Indian buyers.
        </div>
        <div className="flex gap-5 heading">
          <Link href="/how-it-works" className="hover:text-ink">How it works</Link>
          <Link href="/for-lenders" className="hover:text-ink">For lenders</Link>
          <a href="mailto:hello@propcheck.in" className="hover:text-ink">Contact</a>
        </div>
      </div>
      <div className="text-center text-xs text-ink/50 mt-4 font-body">
        We don&apos;t sell listings. We don&apos;t take broker commissions.
      </div>
    </footer>
  );
}
