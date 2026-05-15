/**
 * Builder-name → URL slug normalizer. Mirrors backend/app/util/slug.py
 * exactly so the link from a freshly-rendered report ("Prestige Estates
 * Ltd") resolves to the same `/builder/<slug>` page the backend serves.
 *
 * Keep this in lockstep with the Python implementation. If you change one
 * side, update the other — divergence breaks the link entirely.
 */
const SUFFIX_TOKENS = [
  "private-limited",
  "pvt-ltd",
  "pvt-limited",
  "limited",
  "ltd",
  "llp",
  "inc",
  "corporation",
  "corp",
  "company",
  "co",
  "group",
  "developers",
  "developer",
  "builders",
  "builder",
  "constructions",
  "construction",
  "infrastructure",
  "infra",
  "projects",
  "estates",
  "realty",
  "realtors",
  "properties",
  "homes",
];

export function toBuilderSlug(name: string | null | undefined): string | null {
  if (!name) return null;
  // Strip non-ASCII accents the same way Python's unicodedata.NFKD →
  // ascii('ignore') does for the common Latin-with-accents case.
  let s = name.normalize("NFKD").replace(/[̀-ͯ]/g, "");
  s = s.toLowerCase();
  s = s.replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");
  if (!s) return null;
  let changed = true;
  while (changed) {
    changed = false;
    for (const suf of SUFFIX_TOKENS) {
      if (s.endsWith("-" + suf)) {
        s = s.slice(0, -(suf.length + 1));
        changed = true;
        break;
      }
      if (s === suf) return null;
    }
  }
  return s || null;
}
