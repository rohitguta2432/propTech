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

### Initial seed (5-city coverage)

One curated CSV per metro, each holding ~20 localities × 1/2/3/4 BHK = 80 rows. Static, manually-curated values reflecting May 2026 ₹/sqft — chosen over scrape-and-average to avoid portal blocking and keep the seed deterministic.

Coverage at launch spans **7 distinct cities** across 5 metro CSVs (Delhi NCR is split into the city values that match listing portals' actual `city` field):

| CSV file | `city` values | Localities | Rows |
|---|---|---|---|
| `locality_prices_bangalore.csv` | Bangalore | 20 | 80 |
| `locality_prices_mumbai.csv` | Mumbai | 20 | 80 |
| `locality_prices_delhi.csv` | Delhi (7), Gurgaon (7), Noida (6) | 20 | 80 |
| `locality_prices_pune.csv` | Pune | 20 | 80 |
| `locality_prices_hyderabad.csv` | Hyderabad | 20 | 80 |

Total: ~100 localities × 4 BHK = ~400 rows in `locality_prices`.

```
backend/seeds/locality_prices_bangalore.csv

city,locality,bhk,avg_price_per_sqft,sample_size
Bangalore,Whitefield,1,9800,55
Bangalore,Whitefield,2,10500,210
Bangalore,Whitefield,3,11200,260
Bangalore,Whitefield,4,11900,90
Bangalore,Indiranagar,1,15200,45
...
```

### Interface

```python
async def get_avg_price(city: str, locality: str, bhk: int) -> int | None:
    """Return avg ₹/sqft, or None if not in our index."""
```

### Loader

`scripts/seed_locality_prices.py` — loops over the five city CSVs and upserts each into `locality_prices`. Run once after migration; idempotent (re-runs update existing rows in place).

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
