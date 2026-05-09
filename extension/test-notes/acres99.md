# 99acres — manual test notes

## Known URLs

### Search-results page
- `https://www.99acres.com/property-in-bangalore-ffid` — Bangalore "for sale" SRP
- `https://www.99acres.com/search/property/buy/bangalore-all?city=20&preference=S&area_unit=1&res_com=R` — full SRP with filters

### Detail page
- Pattern: `https://www.99acres.com/<slug>-spid-<ID>` (e.g. `https://www.99acres.com/3-bhk-apartment-in-whitefield-bangalore-spid-X1234567`)
- Alt pattern: `https://www.99acres.com/<slug>-pid-<ID>`
- Alt pattern: `https://www.99acres.com/property-details/<slug>`

## Selectors (for right-click → Inspect on a real page when these break)

### Search cards (any of)
- `.srpTuple_srpTupleBox`
- `[data-testid="srp-tile"]`
- `[class*="srpTuple"]`

### Listing-href anchor inside a card
- `<a>` whose `href` matches `/99acres\.com\/.+(spid|pid)-/i`

### Detail-page detection
- `pathname` contains `-spid-` or `-pid-`
- OR `pathname` contains `/property-details/`

## Debug recipe
1. Visit a search-results URL. Open DevTools → Elements.
2. Right-click a listing card → Inspect. Confirm one of the selectors above still matches the card's outermost wrapper.
3. Check the anchor inside the card has an href matching `LISTING_URL_RE`.
4. If 99acres has rebranded class names, update `CARD_SELECTORS` and `LISTING_URL_RE` in `extension/src/content/acres99.ts`.
