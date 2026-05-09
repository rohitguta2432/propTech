# Integrations Spec

External data sources we wrap. One module per source, all async, fail-soft.

---

## 1. Karnataka RERA — `app/integrations/rera_karnataka.py`

Verifies a RERA project ID against the Karnataka RERA registry.

### Interface

```python
@dataclass
class RERAProject:
    rera_id: str
    project_name: str | None
    builder_name: str | None
    status: str | None              # "registered" | "expired" | "cancelled" | None
    raw: dict | None


class RERAResult:
    status: Literal["MATCH", "MISMATCH", "NOT_FOUND", "NOT_PROVIDED", "PORTAL_UNREACHABLE"]
    project: RERAProject | None     # set when status == "MATCH"


async def lookup(rera_id: str | None) -> RERAResult: ...
```

### Behaviour

- If `rera_id is None`: return `NOT_PROVIDED`.
- Cache lookups in `rera_records` table for 7 days. Hit Postgres first.
- On cache miss, fetch from `https://rera.karnataka.gov.in/projectViewDetails?projectId=<id>` (or whichever endpoint is current).
- Parse the response (HTML or JSON, Karnataka uses HTML).
- On HTTP failure or timeout: return `PORTAL_UNREACHABLE`. Don't cache failures.
- Schema-match: a project is found if `rera_id` exists in the registry, regardless of name.

### Tests

- Fixture HTML for one `MATCH`, one `NOT_FOUND`.
- Mock httpx via `respx` or a manual fixture replay.
- Cache hit/miss covered.

---

## 2. Locality price index — `app/integrations/locality_prices.py`

Stores avg ₹/sqft per (city, locality, bhk) for trust engine's price-deviation signal.

### Initial seed (Bangalore)

A one-time CSV seed for top-20 Bangalore localities × 1/2/3/4 BHK. Source: scrape Magicbricks search pages once and average the listed prices, OR use a static manually-curated seed to avoid blocking.

For MVP, ship a **static curated CSV** of 20 localities × 4 BHK types — that's 80 rows. Bangalore-only at launch.

```
backend/seeds/locality_prices_bangalore.csv

city,locality,bhk,avg_price_per_sqft,sample_size
Bangalore,Whitefield,1,9500,40
Bangalore,Whitefield,2,10200,150
Bangalore,Whitefield,3,10600,200
Bangalore,Whitefield,4,11400,80
Bangalore,Indiranagar,1,15000,30
...
```

### Interface

```python
async def get_avg_price(city: str, locality: str, bhk: int) -> int | None:
    """Return avg ₹/sqft, or None if not in our index."""
```

### Loader

`scripts/seed_locality_prices.py` — reads the CSV and upserts into `locality_prices` table. Run once after migration.

---

## 3. Image hashing — `app/integrations/image_hash.py`

Perceptual hash for stolen-photo detection.

### Interface

```python
async def phash_url(image_url: str) -> int | None:
    """Download image, compute 64-bit pHash, return as int. None on failure."""

async def find_matches(phash: int, threshold: int = 6) -> list[tuple[int, int]]:
    """Find images in DB with Hamming distance ≤ threshold. Returns (image_id, distance) pairs."""
```

### Implementation notes

- Use `imagehash` library + `Pillow`.
- Cap at 4 images per listing for MVP (cost + time).
- Hamming distance via `bin(a ^ b).count('1')`. Done in Python, not SQL — fine at our scale.

### Out of scope at MVP

Bulk reverse-search across the open internet. We only match against listings we've already seen.

---

## Common conventions

- All async functions; never block the event loop.
- All return values either succeed cleanly or return `None` / a typed error variant. Never raise to the caller.
- Caching uses Postgres tables (`rera_records`, `locality_prices`, `images`) — no Redis dependency at this layer.
- Every external HTTP call uses a timeout (5s default).

---

## Tests

Each integration ships with:
- A fixture-replay test (mocked HTTP).
- A "live" test marked `@pytest.mark.live` that hits the real source, only run manually.

---

## Out of scope at MVP

- Maharashtra, Telangana, Tamil Nadu RERA.
- Real reverse image search via Google Vision (saves cost).
- Anti-fraud ML models.

These are Sprint 2.
