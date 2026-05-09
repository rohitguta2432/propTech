"""Pick the right RERA module by inferring state from the rera_id prefix or explicit hint.

This is the single entry point trust-engine code (and any other caller)
should use. It hides per-state portal differences behind one signature.

State coverage:
  - Karnataka    : `rera_karnataka` (default fallback)
  - Maharashtra  : `rera_maharashtra`
  - others       : not yet wired (treat as Karnataka, will return
                   PORTAL_UNREACHABLE / NOT_FOUND from the wrong portal —
                   that's intentional until the relevant module lands).

Inference rules (in order):
  1. `state_hint` argument wins, if provided and recognised.
  2. ID starts with `PRM/KA/` or contains `/KA/`        -> karnataka
  3. ID starts with `P5` or `P0` (MahaRERA pattern)     -> maharashtra
  4. Otherwise                                          -> karnataka (default)
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from app.integrations import rera_karnataka, rera_maharashtra

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from app.integrations.rera_karnataka import RERAResult


# State name -> module mapping. New states get added here once their
# integration module exists.
_MODULES = {
    "karnataka": rera_karnataka,
    "maharashtra": rera_maharashtra,
}

# Default state when nothing else matches. Karnataka is the launch
# market, so unrecognised ids fall back to it (current behaviour
# preserved from before the dispatcher).
_DEFAULT_STATE = "karnataka"


def _infer_state(rera_id: str | None) -> str:
    """Best-effort state inference from the id shape."""
    if not rera_id:
        return _DEFAULT_STATE

    rid = rera_id.strip()
    if not rid:
        return _DEFAULT_STATE

    rid_upper = rid.upper()

    # Karnataka: `PRM/KA/RERA/...` or any id containing `/KA/`.
    if rid_upper.startswith("PRM/KA/") or "/KA/" in rid_upper:
        return "karnataka"

    # Maharashtra: `P52800019287` shape — `P` + 2-digit state code +
    # digits. The two main MahaRERA prefixes in the wild are `P5`
    # (Maharashtra mainland) and `P0` (older / out-of-sequence ids).
    if rid_upper.startswith("P5") or rid_upper.startswith("P0"):
        return "maharashtra"

    return _DEFAULT_STATE


async def lookup(
    rera_id: str | None,
    db: "Session",
    *,
    state_hint: str | None = None,
) -> "RERAResult":
    """Verify a RERA id, dispatching to the right state module.

    Args:
        rera_id:    The RERA registration id (may be None / empty —
                    handled by the underlying module).
        db:         Active SQLAlchemy session for cache reads/writes.
        state_hint: Optional explicit state name (e.g. ``"maharashtra"``).
                    Wins over inference. Unknown values are ignored and
                    we fall back to inference.

    Returns:
        The `RERAResult` produced by the chosen state's module.
    """
    state: str | None = None
    if state_hint:
        normalized = state_hint.strip().lower()
        if normalized in _MODULES:
            state = normalized

    if state is None:
        state = _infer_state(rera_id)

    module = _MODULES.get(state, _MODULES[_DEFAULT_STATE])
    return await module.lookup(rera_id, db)
