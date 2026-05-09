import Link from "next/link";

export function Nav() {
  return (
    <header className="sticky top-0 z-50 bg-cream/85 backdrop-blur border-b border-subtle">
      <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
        <Link href="/" className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-ink flex items-center justify-center">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#d97757" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M9 12l2 2 4-4"/><circle cx="12" cy="12" r="10"/>
            </svg>
          </div>
          <span className="heading font-bold text-lg tracking-tight">PropCheck</span>
        </Link>
        <div className="hidden sm:flex items-center gap-5 text-sm">
          <Link href="/how-it-works" className="text-ink/70 hover:text-ink heading">How it works</Link>
          <Link href="/for-lenders" className="text-ink/70 hover:text-ink heading">For lenders</Link>
        </div>
      </div>
    </header>
  );
}
