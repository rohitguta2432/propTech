# Housing.com — manual test notes

## Known URLs

### Search-results page
- `https://housing.com/in/buy/searches/P52in5xosxi3yng2` — Bangalore-area buy SRP
- `https://housing.com/in/buy/bangalore` — city-level buy index page

### Detail page
- Pattern A: `https://housing.com/in/buy/rd/<slug>/<ID>` (resale unit)
- Pattern B: `https://housing.com/in/buy/ds/<slug>/<ID>` (developer-sale unit)
- Pattern C: `https://housing.com/buy/projects/<slug>/<numeric-id>` (project page)

## Selectors (for right-click → Inspect on a real page when these break)

### Search cards (any of)
- `[data-q="cardCarousel"]`
- `[itemtype$="Residence"]` (schema.org microdata, semi-stable)
- `a[href*="/buy/projects/"]`
- `.css-1k5kf6m` (Emotion-generated, can churn — replace via inspection)
- `[class*="ProjectCard"]`

### Listing-href anchor inside a card
- `<a>` whose `href` matches `/in/buy/(rd|ds)/<slug>/<id>` or `/buy/projects/<slug>/<numeric-id>`

### Detail-page detection
- `pathname` matches `/in/buy/(rd|ds)/<slug>/<id>`
- OR `pathname` matches `/buy/projects/<slug>/<numeric-id>`

## Debug recipe
1. Visit a search-results URL. Open DevTools → Elements.
2. Right-click a listing card → Inspect. Housing's class names are Emotion-generated hashes (e.g. `css-1k5kf6m`). They WILL drift; lean on `[data-q="cardCarousel"]` and `[itemtype$="Residence"]` first.
3. If the Emotion class is now different, replace `.css-1k5kf6m` in `CARD_SELECTORS`.
4. If the URL pattern changes, update `LISTING_URL_RE` AND `isDetailPage()` together — they're paired with the backend `housing.py` parser regex.
