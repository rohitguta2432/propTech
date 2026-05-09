"""Perceptual image hashing integration.

Computes 64-bit perceptual hashes (pHash) of listing photos so the trust
engine can flag the ``STOLEN_PHOTOS`` signal when the same image appears
across multiple listings on multiple portals.

Public surface (see specs/integrations.md §3):

  - ``hamming(a, b)``         : sync helper, Hamming distance between two
                                64-bit integers.
  - ``phash_url(url, ...)``   : download an image, return its 64-bit
                                pHash as a Python int. ``None`` on any
                                failure.
  - ``find_matches(phash, db, ...)``
                              : scan the ``images`` table for rows whose
                                pHash is within Hamming distance
                                ``threshold`` of the given hash. Returns
                                ``(image_id, distance)`` pairs sorted by
                                distance ascending.
  - ``hash_listing(urls, property_id, db, ...)``
                              : convenience wrapper used by the scraper
                                pipeline — hashes up to ``max_images``
                                URLs, persists rows in the ``images``
                                table, and returns the count actually
                                hashed. Idempotent on (property_id, url).

Failure modes (every async function is fail-soft, never raises to the
caller):

  - HTTP timeout / non-200    -> phash_url returns None.
  - Response > 5 MB           -> phash_url returns None (we early-cancel
                                 by checking content-length first; if the
                                 server doesn't advertise it, we read up
                                 to the cap and bail when exceeded).
  - Bytes aren't a valid image -> phash_url returns None.
  - Any other exception        -> caught + logged + returned as None / [] / 0.

The PIL ``Image`` class collides with our ORM ``Image`` model — we import
the ORM model as ``ImageRow`` to keep both names available without
shadowing.
"""
from __future__ import annotations

import io
import logging
from typing import TYPE_CHECKING

import httpx
from PIL import Image as PILImage
from PIL import UnidentifiedImageError
from sqlalchemy import select
from sqlalchemy.orm import Session

# Import the ORM Image as ImageRow so it doesn't collide with PIL.Image.
from app.models.db import Image as ImageRow

if TYPE_CHECKING:  # pragma: no cover — typing-only import to satisfy mypy.
    pass

# imagehash uses scipy under the hood for the DCT.
import imagehash  # noqa: E402

log = logging.getLogger(__name__)

# Maximum image size we'll download. Anything larger is almost certainly
# either a high-res hero shot we don't need or an attempt to DoS us.
MAX_IMAGE_BYTES = 5 * 1024 * 1024  # 5 MB

# Default per-image network timeout. Kept short — we're hashing 4 images
# per listing, so a 4s ceiling caps the whole step at ~16s worst-case.
DEFAULT_TIMEOUT_S = 4.0

# Hamming threshold under which two pHashes are considered "the same image"
# for stolen-photo detection. 6 is the standard imagehash community value
# for pHash @ 64 bits.
DEFAULT_HAMMING_THRESHOLD = 6

# Cap on images persisted per listing. See specs/integrations.md §3.
DEFAULT_MAX_IMAGES = 4

# pHash values are 64 unsigned bits, but `images.phash` is a Postgres
# BIGINT (signed 64-bit) so values with the high bit set won't fit
# directly. We fold to two's-complement for storage and back when reading.
_TWO_64 = 1 << 64
_INT64_MAX = (1 << 63) - 1


def _to_signed_64(value: int) -> int:
    """Map an unsigned 64-bit ``value`` into the signed-int64 range.

    Postgres BIGINT and SQLite INTEGER are both signed 64-bit; storing
    raw unsigned 64-bit pHashes overflows for any value with the top bit
    set (about half of all hashes in practice). Folding to two's
    complement keeps the bit pattern identical so XOR-based Hamming
    still works.
    """
    if value > _INT64_MAX:
        return value - _TWO_64
    return value


def _from_signed_64(value: int) -> int:
    """Inverse of ``_to_signed_64`` — reload as unsigned 64-bit."""
    if value < 0:
        return value + _TWO_64
    return value


# ---------------------------------------------------------------------------
# Hamming distance — sync, called from both phash_url callers and find_matches.
# ---------------------------------------------------------------------------

def hamming(a: int, b: int) -> int:
    """Return the Hamming distance between two integers (popcount of XOR).

    Works for any two integers; for our use case both inputs are
    64-bit pHash values, but the maths is sign-agnostic because the XOR
    of two two's-complement ints has the same bit pattern as the XOR of
    their unsigned counterparts.
    """
    return bin(a ^ b).count("1")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _hash_bytes_to_int(content: bytes) -> int | None:
    """Turn raw image bytes into a 64-bit pHash int.

    Returns None if PIL can't decode the bytes as an image, or if anything
    else goes wrong inside imagehash (we want belt-and-braces fail-soft).
    """
    try:
        with PILImage.open(io.BytesIO(content)) as img:
            # imagehash.phash will internally convert mode if needed, but
            # forcing a load here surfaces broken-PNG style errors before
            # the hash call rather than from inside it.
            img.load()
            phash_obj = imagehash.phash(img)
    except (UnidentifiedImageError, OSError, ValueError):
        # OSError covers "image file is truncated"; ValueError covers a few
        # PIL edge cases on weird inputs.
        return None
    except Exception:  # pragma: no cover — last-ditch safety net
        log.exception("image_hash: unexpected error decoding image bytes")
        return None

    # imagehash hex-encodes the bit array; int(hex, 16) gives us the
    # canonical 64-bit integer representation we store in `images.phash`.
    try:
        return int(str(phash_obj), 16)
    except ValueError:  # pragma: no cover — imagehash always emits valid hex
        return None


async def _download_image_bytes(
    url: str,
    *,
    client: httpx.AsyncClient | None = None,
    timeout_s: float = DEFAULT_TIMEOUT_S,
) -> bytes | None:
    """Fetch the bytes at ``url``, capped at MAX_IMAGE_BYTES.

    - Returns None on HTTP error, timeout, oversized payload, or any
      non-2xx status.
    - If the server advertises ``Content-Length`` and it's over the cap,
      we abort before pulling the body (saves bandwidth on adversarial
      inputs).
    - If the server omits Content-Length (chunked transfer), we stream
      and bail as soon as the running byte total exceeds the cap.
    """
    owns_client = client is None
    try:
        if owns_client:
            client = httpx.AsyncClient(
                timeout=timeout_s, follow_redirects=True
            )

        try:
            # Use a streaming GET so we can cancel mid-download for
            # oversized bodies without buffering the whole thing first.
            async with client.stream("GET", url) as response:
                if response.status_code >= 400:
                    return None

                # Honour the server's advertised size when present.
                content_length = response.headers.get("content-length")
                if content_length is not None:
                    try:
                        if int(content_length) > MAX_IMAGE_BYTES:
                            return None
                    except ValueError:
                        # Malformed header — fall through to streaming check.
                        pass

                buf = bytearray()
                async for chunk in response.aiter_bytes():
                    buf.extend(chunk)
                    if len(buf) > MAX_IMAGE_BYTES:
                        return None
                return bytes(buf)
        except httpx.TimeoutException:
            log.warning("image_hash: timeout downloading %s", url)
            return None
        except httpx.HTTPError:
            log.warning("image_hash: HTTP error downloading %s", url, exc_info=True)
            return None
    finally:
        if owns_client and client is not None:
            await client.aclose()


# ---------------------------------------------------------------------------
# Public API — phash_url
# ---------------------------------------------------------------------------

async def phash_url(
    image_url: str,
    *,
    client: httpx.AsyncClient | None = None,
    timeout_s: float = DEFAULT_TIMEOUT_S,
) -> int | None:
    """Download the image at ``image_url`` and return its 64-bit pHash.

    Args:
        image_url: Absolute URL to a JPEG/PNG/WEBP/etc. image.
        client:    Optional pre-built httpx client (used by tests to inject
                   a respx-mocked client and by scrapers to share a pool).
        timeout_s: Per-request timeout, defaults to 4 seconds.

    Returns:
        A 64-bit Python int on success; ``None`` on any failure (timeout,
        non-image, oversized, network error, etc.). Never raises.
    """
    if not image_url or not isinstance(image_url, str):
        return None

    try:
        content = await _download_image_bytes(
            image_url, client=client, timeout_s=timeout_s
        )
    except Exception:  # pragma: no cover — last-ditch safety net
        log.exception("image_hash.phash_url: download failed for %s", image_url)
        return None

    if content is None:
        return None

    return _hash_bytes_to_int(content)


# ---------------------------------------------------------------------------
# Public API — find_matches
# ---------------------------------------------------------------------------

async def find_matches(
    phash: int,
    db: Session,
    *,
    threshold: int = DEFAULT_HAMMING_THRESHOLD,
    exclude_property_id: int | None = None,
) -> list[tuple[int, int]]:
    """Find images in the DB whose pHash is within ``threshold`` of ``phash``.

    Loads all candidate rows (optionally excluding rows tied to
    ``exclude_property_id``) and computes Hamming distance in Python.
    Fine at our scale; revisit when ``images`` exceeds ~1M rows.

    Returns ``(image_id, distance)`` pairs sorted by distance ascending.
    Returns ``[]`` on any error.
    """
    try:
        stmt = select(ImageRow.id, ImageRow.phash)
        if exclude_property_id is not None:
            stmt = stmt.where(ImageRow.property_id != exclude_property_id)

        rows = db.execute(stmt).all()
    except Exception:  # pragma: no cover — last-ditch safety net
        log.exception("image_hash.find_matches: DB query failed")
        return []

    matches: list[tuple[int, int]] = []
    for image_id, stored_phash in rows:
        if stored_phash is None:
            continue
        # Stored as signed-int64; lift back to unsigned for Hamming.
        unsigned = _from_signed_64(int(stored_phash))
        distance = hamming(phash, unsigned)
        if distance <= threshold:
            matches.append((int(image_id), distance))

    # Closest first — caller usually only cares about the top match.
    matches.sort(key=lambda pair: pair[1])
    return matches


# ---------------------------------------------------------------------------
# Public API — hash_listing
# ---------------------------------------------------------------------------

async def hash_listing(
    listing_image_urls: list[str],
    property_id: int,
    db: Session,
    *,
    max_images: int = DEFAULT_MAX_IMAGES,
) -> int:
    """Hash up to ``max_images`` URLs and persist them under ``property_id``.

    Behaviour:
        - Caps at ``max_images`` URLs (defaults to 4 — see spec).
        - Skips URLs that fail to hash (returns ``None`` from ``phash_url``)
          rather than aborting the batch.
        - Idempotent on ``(property_id, url)`` — if a row already exists for
          a given URL under this property, we skip it (no duplicate
          insertion, and we don't re-fetch the bytes).

    Returns:
        The count of NEW rows inserted into the ``images`` table. URLs that
        were already cached or that failed to hash are not counted.
    """
    if not listing_image_urls:
        return 0

    # Slice up front so we don't even bother with extras.
    urls_to_hash = listing_image_urls[:max_images]

    # Find existing (property_id, url) pairs in one query so we can skip
    # both the network call AND the insert for already-known URLs.
    try:
        existing_rows = db.execute(
            select(ImageRow.url).where(
                ImageRow.property_id == property_id,
                ImageRow.url.in_(urls_to_hash),
            )
        ).all()
        existing_urls = {row[0] for row in existing_rows}
    except Exception:  # pragma: no cover — last-ditch safety net
        log.exception(
            "image_hash.hash_listing: existence query failed for property_id=%s",
            property_id,
        )
        return 0

    inserted = 0
    # Re-use a single AsyncClient across the batch — saves the connection
    # setup cost on the second-through-Nth image.
    async with httpx.AsyncClient(
        timeout=DEFAULT_TIMEOUT_S, follow_redirects=True
    ) as client:
        for url in urls_to_hash:
            if not url or not isinstance(url, str):
                continue
            if url in existing_urls:
                continue

            phash = await phash_url(url, client=client)
            if phash is None:
                # Failed download / decode — skip silently per spec.
                continue

            try:
                db.add(
                    ImageRow(
                        property_id=property_id,
                        url=url,
                        # Fold to signed-int64 for BIGINT storage.
                        phash=_to_signed_64(phash),
                    )
                )
                db.commit()
                inserted += 1
            except Exception:  # pragma: no cover — defensive only
                log.exception(
                    "image_hash.hash_listing: insert failed for property_id=%s url=%s",
                    property_id,
                    url,
                )
                db.rollback()
                continue

    return inserted
