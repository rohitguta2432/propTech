"""Tests for the LLM parsing fallback (Gemma 4 31B via OpenRouter)."""
from __future__ import annotations

import json
from unittest.mock import patch

import httpx
import pytest
import respx

from app.integrations import llm_parser
from app.scrapers.base import ScrapedListing


def _empty_listing() -> ScrapedListing:
    return ScrapedListing(
        portal="magicbricks",
        listing_id="test-1",
        url="https://example.com/x",
    )


def _full_listing() -> ScrapedListing:
    return ScrapedListing(
        portal="magicbricks",
        listing_id="test-1",
        url="https://example.com/x",
        title="3 BHK in Whitefield",
        price_inr=12_000_000,
        bhk=3,
        area_sqft=1450,
        locality="Whitefield",
    )


@pytest.mark.asyncio
async def test_no_op_when_api_key_unset():
    """Without OPENROUTER_API_KEY, never even calls the API."""
    listing = _empty_listing()
    with patch.object(llm_parser.settings, "openrouter_api_key", None):
        out = await llm_parser.enrich("<html>...</html>", listing)
    assert out is listing
    assert out.title is None  # nothing changed


@pytest.mark.asyncio
async def test_no_op_when_listing_already_full():
    """If regex got everything, skip the LLM call."""
    listing = _full_listing()
    with patch.object(llm_parser.settings, "openrouter_api_key", "fake-key"):
        # Should NOT make an HTTP call. respx is not mounted here, so a real
        # HTTP call would hit the network — but the function must short-circuit.
        out = await llm_parser.enrich("<html>...</html>", listing)
    assert out is listing
    assert out.price_inr == 12_000_000


@pytest.mark.asyncio
async def test_fills_missing_fields_from_llm():
    listing = _empty_listing()
    llm_response = {
        "choices": [
            {
                "message": {
                    "content": json.dumps({
                        "title": "3 BHK Apartment",
                        "price_inr": 12_000_000,
                        "bhk": 3,
                        "area_sqft": 1450,
                        "locality": "Whitefield",
                        "city": "Bangalore",
                        "state": "karnataka",
                        "rera_id": "PRM/KA/RERA/1251/446/PR/170820/000123",
                        "builder_name": "ABC Developers",
                    })
                }
            }
        ]
    }
    with respx.mock(base_url="https://openrouter.ai/api/v1") as mock, patch.object(
        llm_parser.settings, "openrouter_api_key", "fake-key"
    ):
        mock.post("/chat/completions").mock(return_value=httpx.Response(200, json=llm_response))
        out = await llm_parser.enrich("<html><body>price ₹1.2 Cr</body></html>", listing)

    assert out.title == "3 BHK Apartment"
    assert out.price_inr == 12_000_000
    assert out.bhk == 3
    assert out.area_sqft == 1450
    assert out.locality == "Whitefield"
    assert out.city == "Bangalore"
    assert out.state == "karnataka"
    assert out.rera_id == "PRM/KA/RERA/1251/446/PR/170820/000123"
    assert out.builder_name == "ABC Developers"


@pytest.mark.asyncio
async def test_regex_wins_when_both_have_value():
    """Regex-extracted fields are NOT overwritten by the LLM."""
    listing = ScrapedListing(
        portal="magicbricks",
        listing_id="test-1",
        url="https://example.com/x",
        price_inr=12_000_000,  # regex got this
        # everything else None
    )
    llm_response = {
        "choices": [
            {
                "message": {
                    "content": json.dumps({
                        "price_inr": 99_999_999,  # LLM tries to overwrite
                        "bhk": 3,                  # LLM fills new field
                    })
                }
            }
        ]
    }
    with respx.mock(base_url="https://openrouter.ai/api/v1") as mock, patch.object(
        llm_parser.settings, "openrouter_api_key", "fake-key"
    ):
        mock.post("/chat/completions").mock(return_value=httpx.Response(200, json=llm_response))
        out = await llm_parser.enrich("<html>x</html>", listing)

    assert out.price_inr == 12_000_000  # regex stayed
    assert out.bhk == 3  # LLM filled the gap


@pytest.mark.asyncio
async def test_strips_markdown_code_fences_in_response():
    """Some models wrap JSON in ```json...``` despite the prompt."""
    listing = _empty_listing()
    llm_response = {
        "choices": [
            {
                "message": {
                    "content": '```json\n{"price_inr": 8500000, "bhk": 2}\n```'
                }
            }
        ]
    }
    with respx.mock(base_url="https://openrouter.ai/api/v1") as mock, patch.object(
        llm_parser.settings, "openrouter_api_key", "fake-key"
    ):
        mock.post("/chat/completions").mock(return_value=httpx.Response(200, json=llm_response))
        out = await llm_parser.enrich("<html>x</html>", listing)

    assert out.price_inr == 8_500_000
    assert out.bhk == 2


@pytest.mark.asyncio
async def test_returns_unchanged_on_http_error():
    listing = _empty_listing()
    with respx.mock(base_url="https://openrouter.ai/api/v1") as mock, patch.object(
        llm_parser.settings, "openrouter_api_key", "fake-key"
    ):
        mock.post("/chat/completions").mock(return_value=httpx.Response(503))
        out = await llm_parser.enrich("<html>x</html>", listing)

    assert out is listing
    assert out.price_inr is None  # unchanged


@pytest.mark.asyncio
async def test_returns_unchanged_on_timeout():
    listing = _empty_listing()
    with respx.mock(base_url="https://openrouter.ai/api/v1") as mock, patch.object(
        llm_parser.settings, "openrouter_api_key", "fake-key"
    ):
        mock.post("/chat/completions").mock(side_effect=httpx.TimeoutException("slow"))
        out = await llm_parser.enrich("<html>x</html>", listing)
    assert out.price_inr is None


@pytest.mark.asyncio
async def test_returns_unchanged_on_invalid_json():
    listing = _empty_listing()
    llm_response = {
        "choices": [
            {"message": {"content": "I'm sorry, I can't comply. Maybe try again?"}}
        ]
    }
    with respx.mock(base_url="https://openrouter.ai/api/v1") as mock, patch.object(
        llm_parser.settings, "openrouter_api_key", "fake-key"
    ):
        mock.post("/chat/completions").mock(return_value=httpx.Response(200, json=llm_response))
        out = await llm_parser.enrich("<html>x</html>", listing)
    assert out.price_inr is None


@pytest.mark.asyncio
async def test_html_is_truncated_before_send():
    """Long HTML is trimmed before going over the wire."""
    listing = _empty_listing()
    huge_html = "<html>" + ("x" * 50_000) + "</html>"

    captured = {}

    def _capture(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        captured["prompt"] = body["messages"][1]["content"]
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "{}"}}]},
        )

    with respx.mock(base_url="https://openrouter.ai/api/v1") as mock, patch.object(
        llm_parser.settings, "openrouter_api_key", "fake-key"
    ):
        mock.post("/chat/completions").mock(side_effect=_capture)
        await llm_parser.enrich(huge_html, listing)

    # Prompt itself is small + 12K trimmed HTML max — never the full 50K.
    assert len(captured["prompt"]) < 14_000


def test_needs_llm_help_thresholds():
    """Function decides when to call the LLM."""
    full = _full_listing()
    assert llm_parser._needs_llm_help(full) is False

    one_missing = _full_listing()
    one_missing.bhk = None
    assert llm_parser._needs_llm_help(one_missing) is False  # only 1 of 4 missing

    two_missing = _full_listing()
    two_missing.bhk = None
    two_missing.locality = None
    assert llm_parser._needs_llm_help(two_missing) is True

    all_missing = _empty_listing()
    assert llm_parser._needs_llm_help(all_missing) is True
