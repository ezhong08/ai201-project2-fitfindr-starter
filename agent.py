"""
agent.py

The FitFindr planning loop. Orchestrates the three tools in response to a
natural language user query, passing state between them via a session dict.

Complete tools.py and test each tool in isolation before implementing this file.

Usage (once implemented):
    from agent import run_agent
    from utils.data_loader import get_example_wardrobe

    result = run_agent(
        query="vintage graphic tee under $30, size M",
        wardrobe=get_example_wardrobe(),
    )
    print(result["fit_card"])
    print(result["error"])   # None on success
"""

import json
import os
import re

from dotenv import load_dotenv
from groq import Groq

from tools import search_listings, suggest_outfit, create_fit_card

load_dotenv()


# ── query parsing ─────────────────────────────────────────────────────────────

# Filler words stripped from the description so only meaningful keywords remain
# for search_listings (which scores by keyword overlap).
_FILLER = {
    "i", "im", "i'm", "am", "a", "an", "the", "some", "me", "please", "for",
    "looking", "want", "need", "find", "searching", "search", "show", "get",
    "wear", "wearing", "mostly", "out", "there", "whats", "what's", "thats",
    "and", "to", "of", "in", "is", "it", "how", "would", "style", "styled",
}

# Word-based size terms mapped to canonical size strings.
_WORD_SIZES = {
    "extra small": "XS",
    "extra large": "XL",
    "small": "S",
    "medium": "M",
    "large": "L",
}


# Prompt for the LLM-based query parser.
_PARSE_QUERY_PROMPT = """\
You are a query parser for a secondhand fashion marketplace. Given a natural-language user query, extract structured search parameters.

Return ONLY a valid JSON object with these keys:
- "description": A space-separated string of meaningful item keywords. Remove filler words like "looking for", "find me", "I want", "please", "show me", "a", "the", "some", "me", "I'm", "I", "is there", "can you", "mostly", "wear", "wearing". Keep descriptors like colors, materials, styles, brands, and item types. Examples: "vintage graphic tee", "black leather jacket", "skinny jeans distressed", "cocktail dress midi formal"
- "size": The clothing size as a canonical code if mentioned. Map word sizes to codes: "extra small"→"XS", "small"→"S", "medium"→"M", "large"→"L", "extra large"→"XL". If the user says "size medium" or just "medium", both map to "M". Keep numeric/raw sizes as-is (e.g., "W30", "US 7", "S/M", "XXS", "W28 L30"). Set to null if no size is mentioned.
- "max_price": The budget ceiling as a number (no currency symbol). Extract from phrases like "under $30", "max 50", "cheaper than 25", "less than 100", "below 40", "< 20", "around 30", or bare "$30". Set to null if no price is mentioned.

Examples:
Query: "vintage graphic tee under $30, size M"
Output: {"description": "vintage graphic tee", "size": "M", "max_price": 30}

Query: "I'm looking for a black leather jacket, medium, max 100 dollars"
Output: {"description": "black leather jacket", "size": "M", "max_price": 100}

Query: "show me some skinny jeans size W28 under 40"
Output: {"description": "skinny jeans", "size": "W28", "max_price": 40}

Query: "find me a cocktail dress for a wedding"
Output: {"description": "cocktail dress wedding", "size": null, "max_price": null}

Query: "designer ballgown size XXS under $5"
Output: {"description": "designer ballgown", "size": "XXS", "max_price": 5}

Query: "I want a medium flannel shirt less than 25"
Output: {"description": "flannel shirt", "size": "M", "max_price": 25}

Query: "size extra small, yoga pants, max $35"
Output: {"description": "yoga pants", "size": "XS", "max_price": 35}
"""


def _parse_query(query: str) -> dict:
    """
    Pull a description, optional size, and optional max_price out of a raw
    natural-language query using an LLM (Groq).

    Returns a dict: {"description": str, "size": str | None, "max_price": float | None}.
    Falls back to a regex-based parser if the LLM call fails for any reason
    (missing API key, network error, malformed response, etc.).
    """
    try:
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            raise ValueError("GROQ_API_KEY not set")
        client = Groq(api_key=api_key)
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "user", "content": _PARSE_QUERY_PROMPT + "\n\nQuery: " + query}
            ],
            temperature=0.0,
        )
        raw = response.choices[0].message.content.strip()
        # Strip markdown code fences if the model wraps the JSON in ```.
        if raw.startswith("```"):
            raw = raw.split("\n", 2)[-1].rsplit("```", 1)[0].strip()
        result = json.loads(raw)
        return {
            "description": str(result.get("description", "")).strip(),
            "size": result.get("size") if result.get("size") is not None else None,
            "max_price": float(result["max_price"]) if result.get("max_price") is not None else None,
        }
    except Exception:
        # Fall back to the regex parser on any failure.
        return _parse_query_regex(query)


def _parse_query_regex(query: str) -> dict:
    """
    [FALLBACK] Pull a description, optional size, and optional max_price out of a raw
    natural-language query using regular expressions.

    Returns a dict: {"description": str, "size": str | None, "max_price": float | None}.
    """
    text = query

    # --- max_price -----------------------------------------------------------
    # Prefer a price cue ("under $30", "max 25", "cheaper than 40", "< 50");
    # fall back to a bare dollar amount ("$30").
    max_price = None
    cue = re.search(
        r"(?:under|below|max(?:imum)?|less than|cheaper than|<)\s*\$?\s*(\d+(?:\.\d+)?)",
        text,
        re.IGNORECASE,
    )
    bare = re.search(r"\$\s*(\d+(?:\.\d+)?)", text)
    match = cue or bare
    if match:
        max_price = float(match.group(1))
        text = text[: match.start()] + " " + text[match.end():]

    # --- size ----------------------------------------------------------------
    # "size M", "size S/M", "size XXS" → take the token after "size".
    size = None
    size_match = re.search(r"\bsize\s+([A-Za-z0-9/]+)", text, re.IGNORECASE)
    if size_match:
        size = size_match.group(1)
        text = text[: size_match.start()] + " " + text[size_match.end():]
    else:
        # Word-based sizes ("medium", "extra small"). Longest first so
        # "extra small" wins over "small".
        for word in sorted(_WORD_SIZES, key=len, reverse=True):
            wm = re.search(rf"\b{re.escape(word)}\b", text, re.IGNORECASE)
            if wm:
                size = _WORD_SIZES[word]
                text = text[: wm.start()] + " " + text[wm.end():]
                break

    # --- description ---------------------------------------------------------
    # Everything left over, minus punctuation and filler words.
    tokens = re.findall(r"[A-Za-z0-9'-]+", text.lower())
    keywords = [t for t in tokens if t not in _FILLER]
    description = " ".join(keywords).strip()

    return {"description": description, "size": size, "max_price": max_price}


# ── session state ─────────────────────────────────────────────────────────────

def _new_session(query: str, wardrobe: dict) -> dict:
    """
    Initialize and return a fresh session dict for one user interaction.

    The session dict is the single source of truth for everything that happens
    during a run — it stores the original query, parsed parameters, tool results,
    and any error that caused early termination.

    You may add fields to this dict as needed for your implementation.
    """
    return {
        "query": query,              # original user query
        "parsed": {},                # extracted description / size / max_price
        "search_results": [],        # list of matching listing dicts
        "selected_item": None,       # top result, passed into suggest_outfit
        "wardrobe": wardrobe,        # user's wardrobe dict
        "outfit_suggestion": None,   # string returned by suggest_outfit
        "fit_card": None,            # string returned by create_fit_card
        "error": None,               # set if the interaction ended early
    }


# ── planning loop ─────────────────────────────────────────────────────────────

def run_agent(query: str, wardrobe: dict) -> dict:
    """
    Main agent entry point. Runs the FitFindr planning loop for a single
    user interaction and returns the completed session dict.

    Args:
        query:    Natural language user request
                  (e.g., "vintage graphic tee under $30, size M")
        wardrobe: User's wardrobe dict — use get_example_wardrobe() or
                  get_empty_wardrobe() from utils/data_loader.py

    Returns:
        The session dict after the interaction completes. Check session["error"]
        first — if it is not None, the interaction ended early and the other
        output fields (outfit_suggestion, fit_card) will be None.

    TODO — implement this function using the planning loop you designed in planning.md:

        Step 1: Initialize the session with _new_session().

        Step 2: Parse the user's query to extract a description, size, and
                max_price. You can use regex, string splitting, or ask the LLM
                to parse it — document your choice in planning.md.
                Store the result in session["parsed"].

        Step 3: Call search_listings() with the parsed parameters.
                Store results in session["search_results"].
                If no results: set session["error"] to a helpful message and
                return the session early. Do NOT proceed to suggest_outfit
                with empty input.

        Step 4: Select the item to use (e.g., the top result).
                Store it in session["selected_item"].

        Step 5: Call suggest_outfit() with the selected item and wardrobe.
                Store the result in session["outfit_suggestion"].

        Step 6: Call create_fit_card() with the outfit suggestion and selected item.
                Store the result in session["fit_card"].

        Step 7: Return the session.

    Before writing code, complete the Planning Loop and State Management sections
    of planning.md — your implementation should match what you described there.
    """
    # Step 1 — create the session (single source of truth for this run).
    session = _new_session(query, wardrobe)

    # Step 2 — parse the raw query into structured search parameters (LLM with regex fallback).
    session["parsed"] = _parse_query(query)

    # Step 3 — search the listings, then branch on the result.
    session["search_results"] = search_listings(
        description=session["parsed"]["description"],
        size=session["parsed"]["size"],
        max_price=session["parsed"]["max_price"],
    )
    if not session["search_results"]:
        session["error"] = (
            f"Sorry — no listings matched '{session['parsed']['description']}'"
            + (
                f" under ${session['parsed']['max_price']:.0f}"
                if session["parsed"]["max_price"]
                else ""
            )
            + ". Try a broader description or a higher budget."
        )
        return session  # early exit — outfit and fit card are never called

    # Step 4 — pick the top (highest-relevance) result.
    session["selected_item"] = session["search_results"][0]

    # Step 5 — suggest an outfit (the tool handles the empty-wardrobe case).
    session["outfit_suggestion"] = suggest_outfit(
        new_item=session["selected_item"],
        wardrobe=session["wardrobe"],
    )

    # Step 6 — build the shareable fit card (the tool guards an empty outfit).
    session["fit_card"] = create_fit_card(
        outfit=session["outfit_suggestion"],
        new_item=session["selected_item"],
    )

    # Step 7 — return the completed session.
    return session


# ── CLI test ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from utils.data_loader import get_example_wardrobe, get_empty_wardrobe

    print("=== Happy path: graphic tee ===\n")
    session = run_agent(
        query="looking for a vintage graphic tee under $30",
        wardrobe=get_example_wardrobe(),
    )
    if session["error"]:
        print(f"Error: {session['error']}")
    else:
        print(f"Found: {session['selected_item']['title']}")
        print(f"\nOutfit: {session['outfit_suggestion']}")
        print(f"\nFit card: {session['fit_card']}")

    print("\n\n=== No-results path ===\n")
    session2 = run_agent(
        query="designer ballgown size XXS under $5",
        wardrobe=get_example_wardrobe(),
    )
    print(f"Error message: {session2['error']}")
