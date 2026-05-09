# Trust Engine — Scoring Rules (v1)

How the 0–100 trust score is computed. Pure rules-based at MVP. Explainable, debuggable, no ML.

---

## Design principles

1. **Explainable**: every signal is a named rule with a public reason. We can always answer *"why this score"*.
2. **Conservative**: when a signal is unclear, we don't dock points. False alarms erode trust faster than missed scams.
3. **Source-cited**: every flag carries a source URL or system name. Buyers can verify our claim.
4. **Composable**: signals are independent. Adding/removing one doesn't require redesigning the engine.
5. **Rules-only in scoring.** No ML / no LLM contributes a score delta. The LLM that does live in the system (`app/integrations/llm_parser.py`) only fills gaps in the upstream parsing layer — it never decides whether a listing is risky. This separation is deliberate: parsing can degrade gracefully, scoring must remain auditable.

---

## Inputs

The engine receives a `PropertyContext` object after parsing + integrations:

```python
@dataclass
class PropertyContext:
    portal: str
    listing_id: str
    title: str
    price_inr: int
    bhk: int
    area_sqft: int
    locality: str
    city: str
    state: str
    rera_id: str | None
    builder_name: str | None
    listed_at: datetime | None
    image_urls: list[str]
    image_phashes: list[int]
    duplicate_listings: list[DuplicateMatch]   # from dedup query
    image_matches_external: int                 # from reverse search
    locality_avg_price_per_sqft: int | None    # from locality_prices
    rera_match: RERAMatchResult                 # MATCH / MISMATCH / NOT_FOUND / NOT_PROVIDED
    builder_open_complaints: int
    builder_delays: int
```

---

## Signals (v1)

Each signal is a function that takes `PropertyContext` and returns either `None` (no flag) or a `Flag`:

```python
@dataclass
class Flag:
    code: str           # e.g. "DUPLICATE_LISTING"
    label: str          # human-readable headline
    description: str    # one sentence explanation
    severity: Literal["high","medium","low","positive"]
    evidence_urls: list[str]
    source: str
    score_delta: int    # negative for red, positive for green
```

### 1. `DUPLICATE_LISTING` — high
Same property listed across multiple portals, especially with different prices.

- **Trigger**: ≥2 duplicates found in `properties` table (matched on locality + bhk + area_sqft within 5%, OR matching image phashes).
- **Severity escalates**: 2 dupes = medium, 3+ = high.
- **Score delta**: −15 (medium) / −25 (high)
- **Description template**: `"Listed {N} times across {M} portals at {K} different prices."`

### 2. `STOLEN_PHOTOS` — high
Listing photos appear on unrelated listings.

- **Trigger**: any listing image's phash matches ≥3 other unrelated `images` rows (different `property_id`).
- **Score delta**: −25
- **Source**: `"Google Vision reverse image search"` (and our own image cache).

### 3. `RERA_MISSING` — medium
No RERA number provided on a listing for a project that should have one (residential >8 units).

- **Trigger**: `rera_id is None AND area_sqft >= 800` (heuristic for "real project, not resale").
- **Score delta**: −10
- **Description**: `"RERA registration not provided. Required for new projects in Karnataka."`

### 4. `RERA_MISMATCH` — high
RERA number provided but no match in state RERA records.

- **Trigger**: `rera_match == 'MISMATCH'` or `'NOT_FOUND'`.
- **Score delta**: −25

### 5. `RERA_OK` — positive
RERA verified.

- **Trigger**: `rera_match == 'MATCH'` AND `rera_record.status == 'registered'`.
- **Score delta**: +10

### 6. `PRICE_BELOW_MARKET` — medium
Listing price >15% below locality avg for same BHK.

- **Trigger**: `(price_per_sqft - avg) / avg <= -0.15`.
- **Score delta**: −10
- **Description template**: `"Price is {pct}% below {locality} {bhk}BHK average. Either a deal or bait."`

### 7. `PRICE_ABOVE_MARKET` — low
Listing price >25% above locality avg for same BHK.

- **Trigger**: `(price_per_sqft - avg) / avg >= 0.25`.
- **Score delta**: −5

### 8. `BUILDER_COMPLAINTS` — medium
Builder has multiple open RERA complaints.

- **Trigger**: `builder_open_complaints >= 3`.
- **Severity by count**: 3–5 = low, 6–10 = medium, 11+ = high.
- **Score delta**: −5 / −10 / −20

### 9. `BUILDER_DELAYS` — low
Builder has reported project delays.

- **Trigger**: `builder_delays >= 1`.
- **Score delta**: −5

### 10. `LISTING_STALE` — low
Listing >180 days old.

- **Trigger**: `now - listed_at > 180 days`.
- **Score delta**: −5
- **Description**: `"This listing is {N} days old. Either ignored or relisted."`

### 11. `LISTING_FRESH` — positive
Listing posted in the last 14 days, by a verified-tag owner.

- **Trigger**: `now - listed_at <= 14 days AND owner_verified == True`.
- **Score delta**: +5

---

## Aggregation formula

```python
def compute_score(context: PropertyContext) -> ScoreResult:
    base = 100
    flags: list[Flag] = []

    for signal_fn in SIGNALS:
        flag = signal_fn(context)
        if flag is not None:
            flags.append(flag)
            base += flag.score_delta

    score = max(0, min(100, base))

    if score >= 70:
        label = "safe"
    elif score >= 40:
        label = "caution"
    else:
        label = "risky"

    return ScoreResult(
        score=score,
        label=label,
        red_flags=[f for f in flags if f.severity != "positive"],
        green_flags=[f for f in flags if f.severity == "positive"],
        summary=_build_summary(flags),
    )
```

**Floor**: even with many compounding deltas, score never goes below 0 or above 100.

---

## Confidence levels

Each flag carries an implicit confidence based on data quality:

| Confidence | Meaning |
|---|---|
| **High** | Direct match against authoritative source (RERA portal, our own deduped DB) |
| **Medium** | Statistical signal (price below avg, image match count) |
| **Low** | Heuristic (listing age, missing RERA on small flat) |

Low-confidence flags get smaller `score_delta` and softer language ("may be", "appears to") in the description.

---

## How to add a new signal

1. Write a function `def signal_xyz(ctx: PropertyContext) -> Flag | None`.
2. Add it to the `SIGNALS` list in `engine/signals/__init__.py`.
3. Add a unit test with a context that triggers and one that doesn't.
4. Document it here in this file (in the same PR).
5. Calibrate the `score_delta` against a sample of 50 real reports.

---

## What v1 explicitly does NOT do

- **No ML / LLM in the scoring engine.** No embeddings, no learned classifiers, no LLM judge. (An LLM IS used in `app/integrations/llm_parser.py` to fill gaps in raw-HTML field extraction when regex fails — that's a parsing concern, not a scoring concern, and the engine treats the resulting fields exactly like regex-extracted ones.)
- No "trust scoring" of brokers or owners by name (legal risk).
- No financial risk assessment.
- No permanent blacklist of any seller.
- No score for properties not yet RERA-required (resales of pre-2017 flats).

These are deferred to v2 once we have data.

---

## Calibration target (90-day MVP)

Run the engine against 100 manually-labelled listings (50 known scams from public scam reports, 50 known clean listings) and aim for:

- **Recall on scams**: ≥ 75%
- **False positive rate on clean**: ≤ 15%
- **Average score for clean**: ≥ 70
- **Average score for scams**: ≤ 40

If we miss these, do not launch publicly until we hit them.
