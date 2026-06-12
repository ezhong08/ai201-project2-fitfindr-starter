"""
Tests for the three FitFindr tools in tools.py.

These cover the happy path and each documented failure mode. The LLM-backed
tools (suggest_outfit, create_fit_card) are tested on their guard/fallback
paths so the suite runs without a live GROQ_API_KEY.
"""

import tools
from tools import search_listings, suggest_outfit, create_fit_card


# A minimal listing dict matching the schema in planning.md.
SAMPLE_ITEM = {
    "id": "lst_999",
    "title": "Vintage Band Tee",
    "description": "Faded graphic tour tee.",
    "category": "tops",
    "style_tags": ["vintage", "graphic tee", "band"],
    "size": "M",
    "condition": "good",
    "price": 22.00,
    "colors": ["black", "white"],
    "brand": None,
    "platform": "depop",
}


# ── search_listings ─────────────────────────────────────────────────────────

def test_search_returns_results():
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert isinstance(results, list)
    assert len(results) > 0


def test_search_empty_results():
    results = search_listings("designer ballgown", size="XXS", max_price=5)
    assert results == []  # empty list, no exception


def test_search_price_filter():
    results = search_listings("jacket", size=None, max_price=10)
    assert all(item["price"] <= 10 for item in results)


def test_search_size_filter():
    results = search_listings("jeans", size="W30", max_price=None)
    assert all("w30" in item["size"].lower() for item in results)


def test_search_sorted_by_relevance():
    # Scores are non-increasing across the returned list.
    results = search_listings("vintage graphic tee", size=None, max_price=None)
    keywords = ["vintage", "graphic", "tee"]

    def score(item):
        haystack = " ".join(
            [item["title"], item["description"], " ".join(item["style_tags"])]
        ).lower()
        return sum(1 for kw in keywords if kw in haystack)

    scores = [score(item) for item in results]
    assert scores == sorted(scores, reverse=True)


# ── suggest_outfit ───────────────────────────────────────────────────────────

def test_suggest_outfit_llm_failure_returns_fallback(monkeypatch):
    # Simulate an LLM/API failure; the tool must return a non-empty fallback.
    def boom():
        raise RuntimeError("API down")

    monkeypatch.setattr(tools, "_get_groq_client", boom)
    result = suggest_outfit(SAMPLE_ITEM, {"items": []})
    assert isinstance(result, str)
    assert result.strip() != ""


def test_suggest_outfit_handles_empty_wardrobe(monkeypatch):
    # Even with an empty wardrobe it returns a usable string (here via fallback).
    monkeypatch.setattr(
        tools, "_get_groq_client", lambda: (_ for _ in ()).throw(RuntimeError())
    )
    result = suggest_outfit(SAMPLE_ITEM, {"items": []})
    assert isinstance(result, str) and result.strip()


# ── create_fit_card ──────────────────────────────────────────────────────────

def test_create_fit_card_empty_outfit_guard():
    msg = create_fit_card("", SAMPLE_ITEM)
    assert msg == "Couldn't generate a fit card — the outfit suggestion was empty."


def test_create_fit_card_whitespace_outfit_guard():
    msg = create_fit_card("   ", SAMPLE_ITEM)
    assert msg == "Couldn't generate a fit card — the outfit suggestion was empty."


def test_create_fit_card_llm_failure_returns_fallback(monkeypatch):
    def boom():
        raise RuntimeError("API down")

    monkeypatch.setattr(tools, "_get_groq_client", boom)
    result = create_fit_card("Pair it with baggy jeans.", SAMPLE_ITEM)
    assert isinstance(result, str)
    assert result.strip() != ""
    # Fallback should still reference the find.
    assert "depop" in result
