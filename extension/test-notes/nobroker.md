# NoBroker — manual test notes

## Known URLs

### Search-results page
- `https://www.nobroker.in/property/sale/bangalore/multiple` — Bangalore for-sale SRP
- `https://www.nobroker.in/flats-for-sale-in-bangalore` — alt SRP entry
- `https://www.nobroker.in/property/rent/bangalore/multiple` — rent SRP (we still badge these)

### Detail page
- Primary pattern: `https://www.nobroker.in/property/<hex-id-8-or-more-chars>/...` (e.g. `https://www.nobroker.in/property/8a9eef4b6c2d/detail`)
- Fallback pattern: any URL ending with a 6+ digit numeric segment (`/123456/`)

## Selectors (for right-click → Inspect on a real page when these break)

### Search cards (any of)
- `.card-container`
- `.cardFlex`
- `[class*="PropertyCard"]`
- `a[href*="/property/"]` (last-ditch, broad)

### Listing-href anchor inside a card
- `<a>` whose `href` matches `/property/<hex-id>` (8+ hex chars) OR ends with `/<6-digit>/?`

### Detail-page detection
- `pathname` matches `/property/[a-f0-9]{8,}`
- OR `pathname` ends with a 6+ digit numeric segment (matches `/123456/?`)

## Debug recipe
1. Visit a search-results URL. Open DevTools → Elements.
2. Right-click a listing card → Inspect. NoBroker tends to use `.card-container` for individual cards inside a flex parent (`.cardFlex`).
3. If new card class names appear (React-rendered, may have hashed suffixes), inspect the wrapper and add to `CARD_SELECTORS`.
4. The numeric-id fallback regex is broad — verify it doesn't match unrelated NoBroker URLs (e.g. /agent/profile/123456) when debugging false-positive sidebar mounts on non-detail pages. Tighten `isDetailPage()` if needed.
