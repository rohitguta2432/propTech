# Multi-state RERA Dispatcher

One Python module per state RERA portal, fronted by a single dispatcher.
Trust-engine and any other caller imports `app.integrations.rera` and
ignores per-state portal differences.

---

## Architecture

```
app/integrations/
├── rera.py                # dispatcher (this spec)
├── rera_karnataka.py      # Karnataka RERA portal — also owns RERAProject / RERAResult
├── rera_maharashtra.py    # MahaRERA portal
└── ...                    # future states
```

`rera_karnataka` defines the `RERAProject` and `RERAResult` dataclasses;
every other state module imports them from there. There is exactly one
result type across the whole system.

---

## Per-state module contract

Every state module MUST export:

```python
async def lookup(rera_id: str | None, db: Session) -> RERAResult: ...
```

Behaviour requirements (mirror `rera_karnataka` — see specs/integrations.md §1):

- `rera_id` is None / blank        → `NOT_PROVIDED`
- 7-day cache via `rera_records`, scoped to the module's `STATE`
- Confirmed 404 / "no record" page → `NOT_FOUND`, placeholder cached
- Timeout / 5xx                    → `PORTAL_UNREACHABLE`, NOT cached
- Unrecognised but real HTML       → `MATCH` with None fields (lossy parser)
- Module must NEVER raise

---

## Dispatcher (`app/integrations/rera.py`)

```python
async def lookup(rera_id, db, *, state_hint=None) -> RERAResult: ...
```

State resolution order:

1. `state_hint` (case-insensitive), if recognised
2. ID starts with `PRM/KA/` or contains `/KA/` → karnataka
3. ID starts with `P5` or `P0`                 → maharashtra
4. Fallback                                    → karnataka (current default)

Unknown `state_hint` values are ignored and inference takes over — never
fail just because a caller passed a state we don't yet support.

---

## State coverage

| State        | Module                | Status |
|--------------|-----------------------|--------|
| Karnataka    | `rera_karnataka.py`   | live   |
| Maharashtra  | `rera_maharashtra.py` | live   |
| Tamil Nadu   | —                     | TBD    |
| Telangana    | —                     | TBD    |
| Delhi NCR    | —                     | TBD    |
| West Bengal  | —                     | TBD    |
| (other)      | —                     | TBD    |

---

## Adding a new state

1. Copy `rera_karnataka.py` to `rera_<state>.py`.
2. Change `STATE` constant and the portal URL in `_fetch_remote`.
3. Tweak the not-found sentinel phrases in `_parse_project_html` for that portal's wording.
4. Reuse `RERAProject` / `RERAResult` (`from app.integrations.rera_karnataka import ...`).
5. Register the module in `app/integrations/rera.py` `_MODULES` and add an inference rule for its id pattern.
6. Mirror `tests/test_rera_maharashtra.py` for the new state.
7. Update the coverage table above.
