"""
tools.py

The three required FitFindr tools. Each tool is a standalone function that
can be called and tested independently before being wired into the agent loop.

Complete and test each tool before moving to agent.py.

Tools:
    search_listings(description, size, max_price)  → list[dict]
    suggest_outfit(new_item, wardrobe)              → str
    create_fit_card(outfit, new_item)               → str
"""

import os

from dotenv import load_dotenv
from groq import Groq

from utils.data_loader import load_listings

load_dotenv()


# ── Groq client ───────────────────────────────────────────────────────────────

def _get_groq_client():
    """Initialize and return a Groq client using GROQ_API_KEY from .env."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError(
            "GROQ_API_KEY not set. Add it to a .env file in the project root."
        )
    return Groq(api_key=api_key)


# ── Tool 1: search_listings ───────────────────────────────────────────────────

def search_listings(
    description: str,
    size: str | None = None,
    max_price: float | None = None,
) -> list[dict]:
    """
    Search the mock listings dataset for items matching the description,
    optional size, and optional price ceiling.

    Args:
        description: Keywords describing what the user is looking for
                     (e.g., "vintage graphic tee").
        size:        Size string to filter by, or None to skip size filtering.
                     Matching is case-insensitive (e.g., "M" matches "S/M").
        max_price:   Maximum price (inclusive), or None to skip price filtering.

    Returns:
        A list of matching listing dicts, sorted by relevance (best match first).
        Returns an empty list if nothing matches — does NOT raise an exception.

    Each listing dict has the following fields:
        id, title, description, category, style_tags (list), size,
        condition, price (float), colors (list), brand, platform

    TODO:
        1. Load all listings with load_listings().
        2. Filter by max_price and size (if provided).
        3. Score each remaining listing by keyword overlap with `description`.
        4. Drop any listings with a score of 0 (no relevant matches).
        5. Sort by score, highest first, and return the listing dicts.

    Before writing code, fill in the Tool 1 section of planning.md.
    """
    listings = load_listings()

    # Tokenize the description into lowercase keywords.
    keywords = description.lower().split()

    results = []
    for listing in listings:
        # Filter by price ceiling (inclusive).
        if max_price is not None and listing["price"] > max_price:
            continue

        # Filter by size (case-insensitive substring match).
        if size is not None and size.lower() not in listing["size"].lower():
            continue

        # Score by keyword overlap across title, description, and style_tags.
        haystack = " ".join(
            [
                listing["title"],
                listing["description"],
                " ".join(listing["style_tags"]),
            ]
        ).lower()
        score = sum(1 for kw in keywords if kw in haystack)

        # Drop listings with no keyword matches.
        if score == 0:
            continue

        results.append((score, listing))

    # Sort by score descending (best match first) and return the listing dicts.
    results.sort(key=lambda pair: pair[0], reverse=True)
    return [listing for _, listing in results]


# ── Tool 2: suggest_outfit ────────────────────────────────────────────────────

def suggest_outfit(
    new_item: dict,
    wardrobe: dict,
    style_profile=None,  # StyleProfile | None
    trend_info: str = "",  # trend analysis string to inject
) -> str:
    """
    Given a thrifted item and the user's wardrobe, suggest 1–2 complete outfits.

    Args:
        new_item:      A listing dict (the item the user is considering buying).
        wardrobe:      A wardrobe dict with an 'items' key containing a list of
                       wardrobe item dicts. May be empty — handle this gracefully.
        style_profile: Optional StyleProfile with preferences learned from past
                       interactions. When non-empty, its summary is appended to
                       the LLM prompt so the suggestion can reference the user's
                       established style tastes.
        trend_info:    Optional trend-analysis string (from trend_analysis()).
                       When non-empty, appended to the prompt so the suggestion
                       can highlight how the outfit aligns with current trends.

    Returns:
        A non-empty string with outfit suggestions.
        If the wardrobe is empty, offer general styling advice for the item
        rather than raising an exception or returning an empty string.

    TODO:
        1. Check whether wardrobe['items'] is empty.
        2. If empty: call the LLM with a prompt for general styling ideas
           (what kinds of items pair well, what vibe it suits, etc.).
        3. If not empty: format the wardrobe items into a prompt and ask
           the LLM to suggest specific outfit combinations using the new item
           and named pieces from the wardrobe.
        4. Return the LLM's response as a string.

    Before writing code, fill in the Tool 2 section of planning.md.
    """
    # print(new_item) # Checking to see if match with dict in handle_query.
    item_summary = (
        f"{new_item.get('title')} "
        f"(category: {new_item.get('category')}, "
        f"colors: {', '.join(new_item.get('colors', []))}, "
        f"style: {', '.join(new_item.get('style_tags', []))}, "
        f"${new_item.get('price')} on {new_item.get('platform')})"
    )

    items = wardrobe.get("items", [])

    # Build extra context snippets injected into the LLM prompt.
    profile_snippet = ""
    if style_profile is not None and not style_profile.is_empty():
        profile_snippet = (
            f"\n\nThe user's style profile (learned from previous searches): "
            f"{style_profile.summary()}. "
            f"Reference these preferences naturally when suggesting outfits — "
            f"note shared aesthetics or complementary styles, but don't force "
            f"a mismatch."
        )

    trend_snippet = ""
    if trend_info:
        trend_snippet = (
            f"\n\nCurrent trend context: {trend_info} "
            f"Work this trend awareness into the outfit suggestion naturally — "
            f"mention why the item feels timely or how to lean into the trend "
            f"with the suggested pairings."
        )

    if not items:
        prompt = (
            "You are a personal stylist for a secondhand-fashion app. "
            "The user doesn't have any wardrobe items saved yet.\n\n"
            f"They're considering this thrifted item: {item_summary}."
            f"{profile_snippet}"
            f"{trend_snippet}\n\n"
            "Suggest general pairings and vibes for this piece — what kinds of "
            "bottoms, shoes, and layers would work with it, what aesthetic it "
            "suits, and what occasions it's great for. Do NOT invent specific "
            "items the user owns. Reply in 2-5 sentences."
        )
    else:
        wardrobe_lines = []
        for it in items:
            line = (
                f"- {it.get('name')} "
                f"(category: {it.get('category')}, "
                f"colors: {', '.join(it.get('colors', []))}, "
                f"style: {', '.join(it.get('style_tags', []))}"
            )
            if it.get("notes"):
                line += f", notes: {it['notes']}"
            line += ")"
            wardrobe_lines.append(line)
        wardrobe_text = "\n".join(wardrobe_lines)

        prompt = (
            "You are a personal stylist for a secondhand-fashion app.\n\n"
            f"The user is considering this thrifted item: {item_summary}.\n\n"
            f"Their wardrobe contains:\n{wardrobe_text}"
            f"{profile_snippet}"
            f"{trend_snippet}\n\n"
            "Suggest 1-2 specific outfit combinations that pair the new item "
            "with named pieces from the wardrobe above. Reference pieces by "
            "their names. Reply in 2-5 sentences."
        )

    try:
        client = _get_groq_client()
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content.strip()
    except Exception:
        return (
            "Try pairing this with your favorite jeans and sneakers for an "
            "easy everyday look."
        )


# ── Tool 3: create_fit_card ───────────────────────────────────────────────────

def create_fit_card(outfit: str, new_item: dict) -> str:
    """
    Generate a short, shareable outfit caption for the thrifted find.

    Args:
        outfit:   The outfit suggestion string from suggest_outfit().
        new_item: The listing dict for the thrifted item.

    Returns:
        A 2–4 sentence string usable as an Instagram/TikTok caption.
        If outfit is empty or missing, return a descriptive error message
        string — do NOT raise an exception.

    The caption should:
    - Feel casual and authentic (like a real OOTD post, not a product description)
    - Mention the item name, price, and platform naturally (once each)
    - Capture the outfit vibe in specific terms
    - Sound different each time for different inputs (use higher LLM temperature)

    TODO:
        1. Guard against an empty or whitespace-only outfit string.
        2. Build a prompt that gives the LLM the item details and the outfit,
           and asks for a caption matching the style guidelines above.
        3. Call the LLM and return the response.

    Before writing code, fill in the Tool 3 section of planning.md.
    """
    if not outfit or not outfit.strip():
        return "Couldn't generate a fit card — the outfit suggestion was empty."

    title = new_item.get("title")
    price = new_item.get("price")
    platform = new_item.get("platform")
    style_tags = ", ".join(new_item.get("style_tags", []))

    prompt = (
        "Write a short Instagram/TikTok-style OOTD caption for a thrifted find.\n\n"
        f"Item: {title}\n"
        f"Price: ${price}\n"
        f"Platform: {platform}\n"
        f"Style tags: {style_tags}\n"
        f"Outfit idea: {outfit}\n\n"
        "Guidelines:\n"
        "- 2-4 sentences.\n"
        "- Mention the item name, price, and platform naturally, once each.\n"
        "- Describe the outfit vibe in specific terms.\n"
        "- Sound casual and authentic, like a real person — not a product listing.\n"
        "Return only the caption text."
    )

    try:
        client = _get_groq_client()
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=1.0,
        )
        return response.choices[0].message.content.strip()
    except Exception:
        return (
            f"Found this {title} on {platform} for ${price} and had to grab it. "
            f"{outfit}"
        )


# ── Tool 4: price_comparison ──────────────────────────────────────────────────

def price_comparison(item: dict, listings: list[dict] | None = None) -> str:
    """
    Compare the price of a listing against similar items in the dataset
    and return an assessment with reasoning.

    Args:
        item:     The listing dict to assess (must have category, price,
                  style_tags, condition, and id).
        listings: The full dataset to compare against. If None, loads from
                  data_loader. Allows the caller to pass in pre-filtered
                  results (e.g., the original search_results) for tighter
                  comparison scoping.

    Returns:
        A string with a price assessment and reasoning — e.g.,
        "At $22.00, this tee is a good deal — similar tops average $27.13
        (range $8.00–$55.00). Among good-condition items the average is $24.50."

    How comparisons are made:
        1. Filter to the same category as the item (tops vs. tops, etc.).
        2. Exclude the item itself (by id) so it doesn't benchmark against itself.
        3. Score each candidate by style-tag overlap with the item — shared tags
           mean shared aesthetic, which makes them better price references.
        4. Keep only candidates with at least one overlapping tag (if any exist);
           otherwise take all same-category items.
        5. Calculate average, minimum, and maximum price across the comparable set.
        6. Optionally compute a condition-specific average (e.g., "good" vs.
           "excellent") and surface it when it differs meaningfully from the
           overall average.
        7. Classify the item's price into one of five tiers:
           - "a great deal"    (< 85 % of average)
           - "a good deal"     (85–95 % of average)
           - "fairly priced"   (95–105 % of average)
           - "slightly above market" (105–120 % of average)
           - "above market"    (> 120 % of average)
    """
    if listings is None:
        listings = load_listings()

    category = item.get("category", "")
    item_price = item.get("price", 0)
    item_id = item.get("id", "")
    item_tags = set(tag.lower() for tag in item.get("style_tags", []))
    item_condition = item.get("condition", "")

    # ── Find comparables ──────────────────────────────────────────────────
    # Same category, exclude self, score by style-tag overlap.
    comparables = []
    for listing in listings:
        if listing.get("id") == item_id:
            continue
        if listing.get("category") != category:
            continue
        listing_tags = set(tag.lower() for tag in listing.get("style_tags", []))
        overlap = len(item_tags & listing_tags)
        comparables.append((overlap, listing))

    if not comparables:
        return (
            f"No comparable {category} listings found in the dataset "
            f"to assess the ${item_price:.2f} price."
        )

    # Sort by tag overlap descending so better matches come first.
    comparables.sort(key=lambda pair: pair[0], reverse=True)

    # Keep only items with at least one overlapping tag, if any exist.
    top_score = comparables[0][0]
    if top_score > 0:
        comparables = [(s, l) for s, l in comparables if s > 0]
    # (If no item has any tag overlap, keep all same-category items.)

    # ── Compute statistics ────────────────────────────────────────────────
    prices = [l["price"] for _, l in comparables]
    avg_price = sum(prices) / len(prices)
    min_price = min(prices)
    max_price = max(prices)
    count = len(comparables)

    # ── Condition-tier breakdown (when it differs meaningfully) ────────────
    condition_prices = [
        l["price"]
        for _, l in comparables
        if l.get("condition") == item_condition
    ]
    condition_note = ""
    if condition_prices and len(condition_prices) >= 2:
        cond_avg = sum(condition_prices) / len(condition_prices)
        if abs(cond_avg - avg_price) / avg_price > 0.10:
            condition_note = (
                f" Among {item_condition}-condition {category} specifically "
                f"({len(condition_prices)} items), the average is ${cond_avg:.2f}."
            )

    # ── Classify ──────────────────────────────────────────────────────────
    ratio = item_price / avg_price if avg_price > 0 else 1.0
    if ratio < 0.85:
        tier = "a great deal"
    elif ratio < 0.95:
        tier = "a good deal"
    elif ratio <= 1.05:
        tier = "fairly priced"
    elif ratio <= 1.20:
        tier = "slightly above market"
    else:
        tier = "above market"

    # ── Build response ────────────────────────────────────────────────────
    return (
        f"Price assessment: At ${item_price:.2f}, this "
        f"{item.get('title', 'item')} is {tier}. "
        f"Compared against {count} similar {category} listings "
        f"(average ${avg_price:.2f}, range ${min_price:.2f}–${max_price:.2f})."
        f"{condition_note}"
    )


# ── Tool 5: trend_analysis ────────────────────────────────────────────────────

# Cache the trends file in memory so we only read it once.
_TRENDS_CACHE: dict | None = None


def _load_trends() -> dict:
    """Load the mock trends dataset (cached)."""
    global _TRENDS_CACHE
    if _TRENDS_CACHE is None:
        import json
        import os

        path = os.path.join(
            os.path.dirname(__file__), "data", "trends.json"
        )
        with open(path, "r", encoding="utf-8") as f:
            _TRENDS_CACHE = json.load(f)
    return _TRENDS_CACHE


def trend_analysis(item: dict) -> str:
    """
    Score a listing against current fashion trends and return an assessment
    that surfaces which trending signals the item hits.

    Args:
        item: The listing dict to assess.  Reads ``style_tags``, ``colors``,
              ``category``, and ``title``.

    Returns:
        A 2–4 sentence string describing how on-trend the item is, with
        specific signal names.  Example:

        *"🔥  On trend (3 signals): vintage style is trending this season,
        'graphic tee' is a hot item right now, and tops are the most
        sought-after category.  The black colorway keeps it versatile."*

    How it works (data source: ``data/trends.json`` — a mock trend report
    simulating aggregator data from runway shows, TikTok hashtags, and
    retail search volume):

        1. Load the trend report (cached).
        2. Score the item across five dimensions:
           - **style tag overlap** — how many of the item's style_tags appear
             in trending_styles.
           - **color overlap** — how many of the item's colors appear in
             trending_colors.
           - **category signal** — whether the item's category is in
             trending_categories.
           - **hot-item match** — whether any word from hot_items appears in
             the item's title or style_tags.
           - **material mentions** — whether the item's description mentions
             any trending_materials (simple substring check).
        3. Build a sentence per matched dimension with specific names.
        4. If zero signals are hit, return a neutral note (the item isn't
           especially timely but isn't off-trend either).
    """
    trends = _load_trends()

    item_tags = [t.lower() for t in item.get("style_tags", [])]
    item_colors = [c.lower() for c in item.get("colors", [])]
    item_category = item.get("category", "").lower()
    item_title = item.get("title", "").lower()
    item_desc = item.get("description", "").lower()

    trending_styles = [s.lower() for s in trends.get("trending_styles", [])]
    trending_colors = [c.lower() for c in trends.get("trending_colors", [])]
    trending_categories = [
        c.lower() for c in trends.get("trending_categories", [])
    ]
    hot_items = [h.lower() for h in trends.get("hot_items", [])]
    trending_materials = [
        m.lower() for m in trends.get("trending_materials", [])
    ]

    signals: list[str] = []
    hit_styles: list[str] = []
    hit_colors: list[str] = []
    hit_items: list[str] = []
    hit_materials: list[str] = []

    # ── 1. Style tag overlap ────────────────────────────────────────────
    for tag in item_tags:
        if tag in trending_styles and tag not in hit_styles:
            hit_styles.append(tag)
    if hit_styles:
        signals.append(
            f"{', '.join(hit_styles)} style{'s' if len(hit_styles) > 1 else ''} "
            f"{'are' if len(hit_styles) > 1 else 'is'} trending this season"
        )

    # ── 2. Color overlap ───────────────────────────────────────────────
    for color in item_colors:
        if color in trending_colors and color not in hit_colors:
            hit_colors.append(color)
    if hit_colors:
        signals.append(
            f"{', '.join(hit_colors)} {'are' if len(hit_colors) > 1 else 'is'} "
            f"a key color this season"
        )

    # ── 3. Category signal ─────────────────────────────────────────────
    if item_category in trending_categories:
        signals.append(
            f"{item_category} {'are' if item_category == 'accessories' else 'is'} "
            f"a trending category right now"
        )

    # ── 4. Hot-item match ──────────────────────────────────────────────
    haystack = f"{item_title} {' '.join(item_tags)} {item_desc}"
    for hot in hot_items:
        if hot in haystack and hot not in hit_items:
            hit_items.append(hot)
    if hit_items:
        signals.append(
            f"{', '.join(hit_items)} {'are' if len(hit_items) > 1 else 'is'} "
            f"a hot item this season"
        )

    # ── 5. Material mentions ───────────────────────────────────────────
    for mat in trending_materials:
        if mat in item_desc and mat not in hit_materials:
            hit_materials.append(mat)
    if hit_materials:
        signals.append(
            f"{', '.join(hit_materials)} is a trending material"
        )

    # ── Build response ─────────────────────────────────────────────────
    signal_count = len(signals)

    if signal_count == 0:
        return (
            f"Trend check: This {item.get('title', 'item')} doesn't hit any "
            f"specific trending signals this season — it's a timeless piece "
            f"that works regardless of what's hot right now."
        )

    # Tier the response
    if signal_count >= 4:
        heat = ">> Very on trend"
    elif signal_count >= 2:
        heat = "> On trend"
    else:
        heat = "- Mildly on trend"

    detail = ".  ".join(signals) + "."
    season = trends.get("season", "this season")

    return (
        f"{heat} ({signal_count} signal{'s' if signal_count > 1 else ''} "
        f"for {season}): {detail}"
    )
