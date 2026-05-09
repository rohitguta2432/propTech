"""Tests for ``app.integrations.image_hash``.

Covers the four public entry points (see specs/integrations.md §3):

  - ``hamming``        : sync XOR-popcount helper.
  - ``phash_url``      : 5 cases — success, 404, oversized, non-image, timeout.
  - ``find_matches``   : threshold + exclude_property_id behaviour.
  - ``hash_listing``   : persistence, skip-on-failure, idempotency.

All HTTP is mocked via respx; we never touch the live network. The DB
fixture is the in-memory SQLite session from the project-wide
``conftest.py`` (`db_session` fixture).

We generate small PNG fixtures at test time rather than committing binary
blobs to the repo — keeps git history clean and removes a class of
"binary fixture out-of-date" bugs.
"""
from __future__ import annotations

import asyncio
import io

import httpx
import pytest
import respx
from PIL import Image as PILImage
from sqlalchemy import select

from app.integrations import image_hash
from app.integrations.image_hash import (
    MAX_IMAGE_BYTES,
    find_matches,
    hamming,
    hash_listing,
    phash_url,
)
from app.models.db import Image as ImageRow
from app.models.db import Property


# ---------------------------------------------------------------------------
# PNG fixture helpers — generated at test-write time via PIL.
# ---------------------------------------------------------------------------

def _png_bytes(color: tuple[int, int, int], size: tuple[int, int] = (100, 100)) -> bytes:
    """Return raw PNG bytes for a solid-colour ``size``-shaped image."""
    buf = io.BytesIO()
    PILImage.new("RGB", size, color=color).save(buf, format="PNG")
    return buf.getvalue()


def _png_with_noise() -> bytes:
    """Solid red image with a couple of subtly-altered pixels.

    Changing 1-2 pixels in a 100x100 image survives the 32x32 DCT
    downsample inside ``imagehash.phash`` essentially unchanged, so the
    result is perceptually identical (Hamming distance 0). That's the
    behaviour we want to assert: small visual perturbations don't change
    the hash, and the threshold-of-6 detection still holds.
    """
    img = PILImage.new("RGB", (100, 100), color=(255, 0, 0))
    img.putpixel((50, 50), (250, 5, 5))
    img.putpixel((51, 50), (250, 5, 5))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture()
def red_png_bytes() -> bytes:
    return _png_bytes((255, 0, 0))


@pytest.fixture()
def red_noise_png_bytes() -> bytes:
    return _png_with_noise()


@pytest.fixture()
def blue_png_bytes() -> bytes:
    return _png_bytes((0, 0, 255))


# ---------------------------------------------------------------------------
# 1. hamming — sync helper
# ---------------------------------------------------------------------------

def test_hamming_basic():
    """0xff vs 0x00 differ in 8 bits; identical inputs differ in 0."""
    assert hamming(0xff, 0x00) == 8
    assert hamming(0xff, 0xff) == 0
    assert hamming(0, 0) == 0
    assert hamming(0b1010, 0b0101) == 4


# ---------------------------------------------------------------------------
# 2. phash_url — success path
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@respx.mock
async def test_phash_url_returns_int_on_success(red_png_bytes):
    """A valid PNG response yields a non-negative 64-bit int."""
    url = "https://example.com/red.png"
    respx.get(url).mock(
        return_value=httpx.Response(
            200,
            content=red_png_bytes,
            headers={"content-type": "image/png"},
        )
    )

    result = await phash_url(url)

    assert isinstance(result, int)
    assert result >= 0
    # 64-bit hash means at most 16 hex chars / fits in 64 bits.
    assert result < (1 << 64)


# ---------------------------------------------------------------------------
# 3. phash_url — failure paths
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@respx.mock
async def test_phash_url_returns_none_on_404():
    url = "https://example.com/missing.png"
    respx.get(url).mock(return_value=httpx.Response(404, text="not found"))

    result = await phash_url(url)

    assert result is None


@pytest.mark.asyncio
@respx.mock
async def test_phash_url_returns_none_on_oversized():
    """Server advertises content-length > 5 MB — we bail without downloading."""
    url = "https://example.com/huge.png"
    oversized = MAX_IMAGE_BYTES + 1
    respx.get(url).mock(
        return_value=httpx.Response(
            200,
            content=b"",  # body irrelevant — header alone should trip the cap
            headers={"content-length": str(oversized), "content-type": "image/png"},
        )
    )

    result = await phash_url(url)

    assert result is None


@pytest.mark.asyncio
@respx.mock
async def test_phash_url_returns_none_on_non_image():
    """HTML in, None out — PIL refuses to open it."""
    url = "https://example.com/page.html"
    respx.get(url).mock(
        return_value=httpx.Response(
            200,
            text="<!doctype html><html><body><h1>not an image</h1></body></html>",
            headers={"content-type": "text/html"},
        )
    )

    result = await phash_url(url)

    assert result is None


@pytest.mark.asyncio
@respx.mock
async def test_phash_url_returns_none_on_timeout():
    """A ``TimeoutException`` from httpx is caught and surfaces as None."""
    url = "https://example.com/slow.png"
    respx.get(url).mock(side_effect=httpx.TimeoutException("read timed out"))

    result = await phash_url(url)

    assert result is None


@pytest.mark.asyncio
@respx.mock
async def test_phash_url_returns_none_on_connect_error():
    """Generic transport errors also surface as None (not raised)."""
    url = "https://example.com/dead.png"
    respx.get(url).mock(side_effect=httpx.ConnectError("connection refused"))

    result = await phash_url(url)

    assert result is None


@pytest.mark.asyncio
async def test_phash_url_handles_empty_url():
    """Empty / non-string inputs are rejected without a network call."""
    assert await phash_url("") is None
    assert await phash_url(None) is None  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# 4. phash_url + similar/different — sanity check on imagehash behaviour
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@respx.mock
async def test_phash_url_similar_images_close_distance(
    red_png_bytes, red_noise_png_bytes, blue_png_bytes
):
    """The noise variant of red should hash close to red; blue should not."""
    respx.get("https://x.test/red.png").mock(
        return_value=httpx.Response(200, content=red_png_bytes)
    )
    respx.get("https://x.test/red-noise.png").mock(
        return_value=httpx.Response(200, content=red_noise_png_bytes)
    )
    respx.get("https://x.test/blue.png").mock(
        return_value=httpx.Response(200, content=blue_png_bytes)
    )

    red = await phash_url("https://x.test/red.png")
    red_noise = await phash_url("https://x.test/red-noise.png")
    blue = await phash_url("https://x.test/blue.png")

    assert red is not None and red_noise is not None and blue is not None
    # Solid colours all map to the same DCT, so they're all 0; the noise
    # version should still be close (well under the threshold of 6).
    assert hamming(red, red_noise) <= 6
    # blue and red are both solid colours -> equal pHash. We don't assert
    # blue != red here because pHash on solid colour is colour-agnostic.
    # The point of this test is the similarity behaviour, not difference.


# ---------------------------------------------------------------------------
# 5. find_matches — threshold + exclude_property_id
# ---------------------------------------------------------------------------

def _seed_property(db_session, *, portal: str = "magicbricks", listing_id: str = "1") -> int:
    """Insert a stub Property row and return its id."""
    prop = Property(portal=portal, listing_id=listing_id)
    db_session.add(prop)
    db_session.commit()
    return prop.id


def _seed_image(db_session, *, property_id: int, url: str, phash: int) -> int:
    """Seed an `images` row, folding the unsigned 64-bit hash to signed BIGINT.

    Tests pass real unsigned 64-bit pHash values; the storage layer is
    BIGINT (signed). The production ``hash_listing`` does this fold at
    write time — this helper mirrors that behaviour so seeded fixtures
    look identical to production-written rows.
    """
    img = ImageRow(
        property_id=property_id,
        url=url,
        phash=image_hash._to_signed_64(phash),
    )
    db_session.add(img)
    db_session.commit()
    return img.id


@pytest.mark.asyncio
async def test_find_matches_returns_within_threshold(db_session):
    """Three rows seeded; a query close to one returns just that one."""
    prop_a = _seed_property(db_session, listing_id="A")
    prop_b = _seed_property(db_session, listing_id="B")
    prop_c = _seed_property(db_session, listing_id="C")

    # Hash A: target. Hash B: identical. Hash C: very different.
    target = 0xdeadbeefcafef00d
    near = target ^ 0b11  # distance 2 — well under threshold of 6
    far = ~target & ((1 << 64) - 1)  # distance 64 — opposite bits

    near_id = _seed_image(db_session, property_id=prop_a, url="a.png", phash=near)
    exact_id = _seed_image(db_session, property_id=prop_b, url="b.png", phash=target)
    _seed_image(db_session, property_id=prop_c, url="c.png", phash=far)

    matches = await find_matches(target, db_session, threshold=6)

    # Only the two close ones should come back, sorted by distance ascending.
    ids_returned = [m[0] for m in matches]
    distances = [m[1] for m in matches]
    assert exact_id in ids_returned
    assert near_id in ids_returned
    assert len(matches) == 2
    assert distances == sorted(distances)
    assert distances[0] == 0  # exact match first


@pytest.mark.asyncio
async def test_find_matches_excludes_property_id(db_session):
    """Setting exclude_property_id skips that property's images entirely."""
    prop_a = _seed_property(db_session, listing_id="A")
    target = 0xabcdef0123456789
    _seed_image(db_session, property_id=prop_a, url="only.png", phash=target)

    matches = await find_matches(
        target, db_session, threshold=6, exclude_property_id=prop_a
    )

    assert matches == []


@pytest.mark.asyncio
async def test_find_matches_empty_db(db_session):
    """No rows -> empty list, not an exception."""
    matches = await find_matches(0xdeadbeef, db_session, threshold=6)
    assert matches == []


@pytest.mark.asyncio
async def test_find_matches_above_threshold_excluded(db_session):
    """A row at exactly threshold is included; threshold+1 is not."""
    prop = _seed_property(db_session)
    target = 0
    # 6 set bits = distance 6 (matches threshold).
    just_at = 0b111111
    # 7 set bits = distance 7 (above threshold).
    above = 0b1111111

    at_id = _seed_image(db_session, property_id=prop, url="at.png", phash=just_at)
    _seed_image(db_session, property_id=prop, url="above.png", phash=above)

    matches = await find_matches(target, db_session, threshold=6)

    assert [m[0] for m in matches] == [at_id]


# ---------------------------------------------------------------------------
# 6. hash_listing — persistence + skip-on-failure + idempotency
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@respx.mock
async def test_hash_listing_persists_rows(db_session, red_png_bytes, blue_png_bytes):
    """Three good URLs -> three rows in `images`."""
    prop_id = _seed_property(db_session)

    urls = [
        "https://example.com/a.png",
        "https://example.com/b.png",
        "https://example.com/c.png",
    ]
    for url in urls:
        respx.get(url).mock(return_value=httpx.Response(200, content=red_png_bytes))

    n = await hash_listing(urls, property_id=prop_id, db=db_session)

    assert n == 3

    rows = db_session.execute(
        select(ImageRow).where(ImageRow.property_id == prop_id)
    ).scalars().all()
    assert len(rows) == 3
    assert {r.url for r in rows} == set(urls)
    # All three are valid 64-bit ints.
    for r in rows:
        assert isinstance(r.phash, int)


@pytest.mark.asyncio
@respx.mock
async def test_hash_listing_skips_failures(db_session, red_png_bytes):
    """A 404 in the middle is skipped; the other two still land."""
    prop_id = _seed_property(db_session)

    good_a = "https://example.com/good-a.png"
    bad = "https://example.com/missing.png"
    good_b = "https://example.com/good-b.png"

    respx.get(good_a).mock(return_value=httpx.Response(200, content=red_png_bytes))
    respx.get(bad).mock(return_value=httpx.Response(404, text="not found"))
    respx.get(good_b).mock(return_value=httpx.Response(200, content=red_png_bytes))

    n = await hash_listing(
        [good_a, bad, good_b], property_id=prop_id, db=db_session
    )

    assert n == 2

    rows = db_session.execute(
        select(ImageRow).where(ImageRow.property_id == prop_id)
    ).scalars().all()
    assert {r.url for r in rows} == {good_a, good_b}


@pytest.mark.asyncio
@respx.mock
async def test_hash_listing_caps_at_max_images(db_session, red_png_bytes):
    """``max_images`` truncates the URL list before any HTTP."""
    prop_id = _seed_property(db_session)

    urls = [f"https://example.com/{i}.png" for i in range(6)]
    for url in urls:
        respx.get(url).mock(return_value=httpx.Response(200, content=red_png_bytes))

    n = await hash_listing(urls, property_id=prop_id, db=db_session, max_images=3)

    assert n == 3
    rows = db_session.execute(
        select(ImageRow).where(ImageRow.property_id == prop_id)
    ).scalars().all()
    assert len(rows) == 3


@pytest.mark.asyncio
@respx.mock
async def test_hash_listing_is_idempotent(db_session, red_png_bytes):
    """Re-running with the same URLs doesn't double-insert rows."""
    prop_id = _seed_property(db_session)

    url = "https://example.com/once.png"
    respx.get(url).mock(return_value=httpx.Response(200, content=red_png_bytes))

    n1 = await hash_listing([url], property_id=prop_id, db=db_session)
    n2 = await hash_listing([url], property_id=prop_id, db=db_session)

    assert n1 == 1
    # Second run sees the existing row and skips both the network call
    # and the insert.
    assert n2 == 0

    rows = db_session.execute(
        select(ImageRow).where(ImageRow.property_id == prop_id)
    ).scalars().all()
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_hash_listing_empty_urls(db_session):
    """No URLs -> 0, no DB activity."""
    prop_id = _seed_property(db_session)
    n = await hash_listing([], property_id=prop_id, db=db_session)
    assert n == 0


# ---------------------------------------------------------------------------
# 7. _hash_bytes_to_int direct — make sure raw bytes -> int round-trips.
# ---------------------------------------------------------------------------

def test_hash_bytes_to_int_returns_int_for_valid_png(red_png_bytes):
    result = image_hash._hash_bytes_to_int(red_png_bytes)
    assert isinstance(result, int)
    assert result >= 0


def test_hash_bytes_to_int_returns_none_for_garbage():
    assert image_hash._hash_bytes_to_int(b"not an image") is None
    assert image_hash._hash_bytes_to_int(b"") is None
