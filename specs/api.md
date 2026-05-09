# API Specification

Source of truth for all backend endpoints. FastAPI, Python 3.11+.

Base URL: `https://api.propcheck.in` (production) · `http://localhost:8000` (dev)
All endpoints prefixed `/v1/`.

---

## Conventions

- **Auth**: Free tier = no auth (rate-limited by IP). Pro + B2B = `X-API-Key` header.
- **Content-Type**: `application/json` for both request and response.
- **Errors**: standard problem-detail JSON. See [Error Format](#error-format) below.
- **Rate limits**: 10 checks/min/IP free. 120/min for Pro keys.
- **Idempotency**: `POST /v1/check` is idempotent on the URL — repeated calls within 24h return the cached report.

---

## Endpoints

### `POST /v1/check`

Submit a property listing URL for trust evaluation.

**Request**
```json
{ "url": "https://www.magicbricks.com/propertyDetails/3-BHK-..." }
```

**Response 200**
```json
{
  "id": "chk_a3f2c1d0",
  "score": 42,
  "label": "risky",
  "summary": "This listing has 4 high-risk signals.",
  "property": {
    "portal": "magicbricks",
    "listing_id": "12345",
    "title": "3 BHK Apartment in Whitefield",
    "price_inr": 12000000,
    "bhk": 3,
    "area_sqft": 1450,
    "locality": "Whitefield",
    "city": "Bangalore",
    "state": "karnataka",
    "rera_id": "PRM/KA/RERA/...",
    "builder_name": "ABC Developers",
    "listed_at": "2026-02-10T08:00:00Z"
  },
  "red_flags": [
    {
      "code": "DUPLICATE_LISTING",
      "label": "Duplicate listings detected",
      "description": "Listed 4 times across 3 portals at 3 different prices.",
      "severity": "high",
      "evidence_urls": [
        "https://magicbricks.com/...",
        "https://99acres.com/...",
        "https://housing.com/..."
      ],
      "source": "PropCheck dedup engine"
    }
  ],
  "green_flags": [],
  "checklist": [
    "Visit the property in person before paying any token",
    "Ask for the sale deed",
    "Verify property tax record at the municipal portal",
    "Never pay token over UPI to a personal account",
    "Verify owner identity with Aadhaar + utility bill"
  ],
  "verifications": {
    "rera": { "status": "MISMATCH", "expected": "any-karnataka-record", "found": null },
    "image_match_count": 7,
    "locality_avg_price_per_sqft": 10600,
    "price_delta_pct": -22,
    "listing_age_days": 87,
    "builder_open_complaints": 6
  },
  "checked_at": "2026-05-09T11:30:00Z",
  "cache_hit": false
}
```

**Errors**
- `400 INVALID_URL` — URL doesn't match a supported portal regex
- `429 RATE_LIMITED` — too many requests
- `502 PORTAL_UNREACHABLE` — couldn't fetch the listing
- `503 ENGINE_ERROR` — internal trust engine failure

---

### `GET /v1/check/{id}`

Fetch a previously generated report.

**Response 200**: same shape as `POST /v1/check`.
**Errors**: `404 NOT_FOUND` if the id does not exist.

---

### `GET /v1/portals`

List portals currently supported by the parser.

**Response 200**
```json
{
  "portals": [
    { "id": "magicbricks", "name": "Magicbricks",  "enabled": true,  "url_regex": "magicbricks\\.com/propertyDetails/" },
    { "id": "99acres",     "name": "99acres",      "enabled": true,  "url_regex": "99acres\\.com/.*-pid-" },
    { "id": "housing",     "name": "Housing.com",  "enabled": true,  "url_regex": "housing\\.com/in/buy/" },
    { "id": "nobroker",    "name": "NoBroker",     "enabled": true,  "url_regex": "nobroker\\.in/property/" }
  ]
}
```

---

### `POST /v1/feedback`

User flags a wrong score for review.

**Request**
```json
{
  "check_id": "chk_a3f2c1d0",
  "reason": "false_positive",
  "note": "I verified the RERA in person, it's correct.",
  "reporter_email": "user@example.com"
}
```

`reason` enum: `false_positive` | `false_negative` | `data_error` | `other`.

**Response 201**
```json
{ "id": 42, "status": "pending" }
```

---

### `POST /v1/whatsapp/webhook`

Twilio inbound webhook. Not called by clients directly. Parses message, runs check, replies via Twilio.

**Headers**: `X-Twilio-Signature` (verified server-side).

**Response 200**: TwiML XML.

---

### `GET /healthz`

Liveness probe. No auth.

**Response 200**
```json
{ "status": "ok", "version": "0.1.0", "uptime_s": 3621 }
```

---

## Error format

All non-2xx responses follow [RFC 7807](https://datatracker.ietf.org/doc/html/rfc7807):

```json
{
  "type": "https://propcheck.in/errors/invalid-url",
  "title": "Invalid URL",
  "status": 400,
  "detail": "The submitted URL does not match any supported portal pattern.",
  "code": "INVALID_URL",
  "trace_id": "01HV..."
}
```

---

## Rate limiting

- Headers on every response:
  - `X-RateLimit-Limit: 10`
  - `X-RateLimit-Remaining: 7`
  - `X-RateLimit-Reset: 1717059600`
- Algorithm: token bucket per IP (or per API key for paid).
- Implementation: Redis-backed via `slowapi` (FastAPI extension).

---

## Versioning

- All routes prefixed `/v1/`. Breaking changes ship under `/v2/`.
- Non-breaking changes (new fields, new flag codes) ship in `/v1/` without a version bump.
- Deprecated fields stay for 6 months with `Deprecation` header.
