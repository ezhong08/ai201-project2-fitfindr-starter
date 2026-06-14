"""
smoke_test.py — FitFindr driver for programmatic interaction.

Tests the full FitFindr pipeline by calling run_agent() directly with a
variety of queries. This is the primary agent-facing interface for verifying
that tools, the planning loop, and query parsing all work correctly.

Usage:
    python .claude/skills/run-fitfindr/smoke_test.py

Exit code 0 = all tests passed. Non-zero = at least one test failed.
"""

import sys
import os

# Ensure the project root is on sys.path so we can import agent/tools.
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from agent import run_agent, _parse_query
from tools import search_listings, suggest_outfit, create_fit_card
from utils.data_loader import get_example_wardrobe, get_empty_wardrobe, load_listings


PASS = 0
FAIL = 0


def check(label: str, condition: bool, detail: str = ""):
    """Assert-like helper that prints result and tallies pass/fail."""
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  PASS  {label}")
    else:
        FAIL += 1
        print(f"  FAIL  {label}  ← {detail}")


def section(title: str):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


# ── Tool 1: search_listings ────────────────────────────────────────────────────

def test_search_listings():
    section("Tool 1: search_listings")

    # Happy path — should find graphic tees.
    results = search_listings("vintage graphic tee")
    check("finds results for 'vintage graphic tee'",
          len(results) > 0,
          f"got {len(results)} results")
    if results:
        check("first result has expected keys",
              all(k in results[0] for k in ("id", "title", "price", "category", "platform")),
              f"keys: {list(results[0].keys())}")
        check("results sorted by relevance",
              results[0].get("title", "").lower().find("tee") >= 0 or
              results[0].get("title", "").lower().find("graphic") >= 0,
              f"top result: {results[0].get('title', '')}")

    # Price filter.
    results_cheap = search_listings("jeans", max_price=30)
    check("max_price filter works",
          all(r["price"] <= 30 for r in results_cheap),
          f"prices: {[r['price'] for r in results_cheap]}")

    # No results.
    results_none = search_listings("designer ballgown", size="XXS", max_price=5)
    check("returns empty list for no matches",
          results_none == [],
          f"got {len(results_none)} results (expected [])")


# ── Tool 2: suggest_outfit ─────────────────────────────────────────────────────

def test_suggest_outfit():
    section("Tool 2: suggest_outfit")
    listings = load_listings()
    item = listings[0]  # Vintage Levi's 501 Jeans

    # With wardrobe.
    wardrobe = get_example_wardrobe()
    result = suggest_outfit(item, wardrobe)
    check("returns non-empty string (with wardrobe)",
          bool(result and result.strip()),
          f"got: {repr(result)}")
    check("mentions item name or category",
          item["title"].split("—")[0].strip().lower() in result.lower() or
          item["category"].lower() in result.lower() or
          "jeans" in result.lower() or
          "denim" in result.lower(),
          f"result: {result[:120]}...")

    # Without wardrobe (empty).
    empty = get_empty_wardrobe()
    result_empty = suggest_outfit(item, empty)
    check("returns non-empty string (empty wardrobe)",
          bool(result_empty and result_empty.strip()),
          f"got: {repr(result_empty)}")
    check("does NOT mention specific wardrobe items",
          "baggy straight-leg jeans" not in result_empty.lower() and
          "chunky white sneakers" not in result_empty.lower(),
          "mentions specific items in empty-wardrobe response")


# ── Tool 3: create_fit_card ─────────────────────────────────────────────────────

def test_create_fit_card():
    section("Tool 3: create_fit_card")
    listings = load_listings()
    item = listings[0]
    outfit = "Pair these jeans with a white tee and sneakers."

    # Happy path.
    card = create_fit_card(outfit, item)
    check("returns non-empty string",
          bool(card and card.strip()),
          f"got: {repr(card)}")
    price_str = f"${item['price']:.1f}".replace(".0", "")
    check("mentions platform",
          item["platform"].lower() in card.lower(),
          f"card: {card[:120]}...")

    # Empty outfit guard.
    card_empty = create_fit_card("", item)
    check("returns error for empty outfit",
          "couldn't" in card_empty.lower(),
          f"got: {repr(card_empty)}")

    card_whitespace = create_fit_card("   ", item)
    check("returns error for whitespace-only outfit",
          "couldn't" in card_whitespace.lower(),
          f"got: {repr(card_whitespace)}")


# ── Query parsing ──────────────────────────────────────────────────────────────

def test_query_parsing():
    section("Query parsing (_parse_query)")

    parsed = _parse_query("vintage graphic tee under $30, size M")
    check("extracts description",
          "graphic" in parsed["description"] or "vintage" in parsed["description"],
          f"description: {parsed['description']}")
    check("extracts size M",
          parsed["size"] == "M",
          f"size: {parsed['size']}")
    check("extracts max_price",
          parsed["max_price"] == 30.0,
          f"max_price: {parsed['max_price']}")

    # No size or price.
    parsed2 = _parse_query("cocktail dress for a wedding")
    check("size is None when not mentioned",
          parsed2["size"] is None,
          f"size: {parsed2['size']}")
    check("max_price is None when not mentioned",
          parsed2["max_price"] is None,
          f"max_price: {parsed2['max_price']}")


# ── Agent loop: full pipeline ──────────────────────────────────────────────────

def test_agent_loop():
    section("Agent loop (run_agent)")

    # Happy path — example wardrobe.
    session = run_agent("vintage graphic tee under $30", get_example_wardrobe())
    check("no error on happy path",
          session["error"] is None,
          f"error: {session['error']}")
    check("has search results",
          len(session["search_results"]) > 0,
          f"got {len(session['search_results'])} results")
    check("has selected item",
          session["selected_item"] is not None)
    check("has outfit suggestion",
          bool(session["outfit_suggestion"] and session["outfit_suggestion"].strip()))
    check("has fit card",
          bool(session["fit_card"] and session["fit_card"].strip()))

    # Happy path — empty wardrobe.
    session2 = run_agent("black leather jacket", get_empty_wardrobe())
    check("empty wardrobe: no error",
          session2["error"] is None,
          f"error: {session2['error']}")
    check("empty wardrobe: has outfit suggestion (general styling)",
          bool(session2["outfit_suggestion"] and session2["outfit_suggestion"].strip()))
    check("empty wardrobe: has fit card",
          bool(session2["fit_card"] and session2["fit_card"].strip()))

    # No-results path.
    session3 = run_agent("designer ballgown size XXS under $5", get_example_wardrobe())
    check("no-results: error is set",
          session3["error"] is not None,
          f"error: {session3['error']}")
    check("no-results: outfit is None",
          session3["outfit_suggestion"] is None)
    check("no-results: fit_card is None",
          session3["fit_card"] is None)
    check("no-results: error message is helpful",
          "sorry" in session3["error"].lower() and "try" in session3["error"].lower(),
          f"error: {session3['error']}")


# ── main ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("  FitFindr Smoke Test")
    print("=" * 60)

    # Check prerequisites.
    section("Prerequisites check")
    api_key = os.environ.get("GROQ_API_KEY")
    check("GROQ_API_KEY is set",
          bool(api_key),
          "Set GROQ_API_KEY in .env file")

    listings = load_listings()
    check("listings data loads",
          len(listings) == 40,
          f"got {len(listings)} listings (expected 40)")

    wardrobe = get_example_wardrobe()
    check("example wardrobe loads",
          len(wardrobe["items"]) == 10,
          f"got {len(wardrobe['items'])} items (expected 10)")

    # Run tests.
    test_search_listings()
    test_suggest_outfit()
    test_create_fit_card()
    test_query_parsing()
    test_agent_loop()

    # Summary.
    total = PASS + FAIL
    print(f"\n{'='*60}")
    print(f"  Results: {PASS}/{total} passed")
    print(f"{'='*60}")

    if FAIL > 0:
        print(f"\n  {FAIL} test(s) FAILED.")
        sys.exit(1)
    else:
        print(f"\n  All {PASS} tests passed!")
        sys.exit(0)
