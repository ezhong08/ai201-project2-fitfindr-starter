# FitFindr 🛍️

A secondhand-fashion shopping assistant that takes natural-language queries, searches a marketplace of thrifted listings, and returns outfit recommendations with shareable fit cards — all powered by an LLM-driven agent loop.

---

## Table of Contents

- [Setup](#setup)
- [Project Structure](#project-structure)
- [Tool Inventory](#tool-inventory)
  - [Tool 1: `search_listings`](#tool-1-search_listings)
  - [Tool 2: `suggest_outfit`](#tool-2-suggest_outfit)
  - [Tool 3: `create_fit_card`](#tool-3-create_fit_card)
- [Planning Loop](#planning-loop)
- [State Management](#state-management)
- [Query Parsing](#query-parsing)
- [Error Handling](#error-handling)
- [Spec Reflection](#spec-reflection)

---

## Setup

```bash
pip install -r requirements.txt
```

Set your Groq API key in a `.env` file (get a free key at [console.groq.com](https://console.groq.com)):

```
GROQ_API_KEY=your_key_here
```

### Running the App

```bash
python app.py
```

Opens a Gradio UI at `http://localhost:7860` (check your terminal — the port may differ).

### CLI Quick Test

```bash
python agent.py
```

Runs two end-to-end tests: a happy-path query and a deliberate no-results query.

---

## Project Structure

```
ai201-project2-fitfindr-starter/
├── data/
│   ├── listings.json            # 40 mock secondhand listings
│   └── wardrobe_schema.json     # Wardrobe format + example wardrobe (10 items)
├── utils/
│   └── data_loader.py           # Loaders for listings and wardrobes
├── tools.py                     # Three standalone tool functions
├── agent.py                     # Query parser + planning loop (run_agent)
├── app.py                       # Gradio web interface
├── planning.md                  # Planning document (design decisions)
├── requirements.txt             # Python dependencies
└── README.md                    # This file
```

---

## Tool Inventory

### Tool 1: `search_listings`

|             |                                                                                                                  |
| ----------- | ---------------------------------------------------------------------------------------------------------------- |
| **Purpose** | Search the 40-item mock listings dataset for items matching a description, with optional size and price filters. |
| **File**    | [tools.py](tools.py#L39-L105)                                                                                    |

**Inputs:**

| Parameter     | Type            | Description                                                                                                                                                          |
| ------------- | --------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `description` | `str`           | Space-separated keywords (e.g., `"vintage graphic tee"`). Split into tokens and scored by keyword overlap against each listing's title, description, and style tags. |
| `size`        | `str \| None`   | Size string to filter by. Matching is case-insensitive and uses substring containment — `"M"` matches `"S/M"` and `"M/L"`. Pass `None` to skip size filtering.       |
| `max_price`   | `float \| None` | Maximum price ceiling (inclusive). Listings with `price > max_price` are dropped. Pass `None` to skip price filtering.                                               |

**Output:** `list[dict]` — matching listing dicts sorted by relevance score descending (best match first). Each dict has these fields:

| Field         | Type          | Example                                                          |
| ------------- | ------------- | ---------------------------------------------------------------- |
| `id`          | `str`         | `"lst_012"`                                                      |
| `title`       | `str`         | `"Vintage Band Tee — The Smiths 1987 Tour"`                      |
| `description` | `str`         | `"Authentic vintage tour tee. Faded graphic, no holes."`         |
| `category`    | `str`         | `"tops"`, `"bottoms"`, `"outerwear"`, `"shoes"`, `"accessories"` |
| `style_tags`  | `list[str]`   | `["vintage", "graphic tee", "band", "90s", "grunge"]`            |
| `size`        | `str`         | `"M"`, `"S/M"`, `"W30 L30"`, `"US 7"`                            |
| `condition`   | `str`         | `"excellent"`, `"good"`, or `"fair"`                             |
| `price`       | `float`       | `22.00`                                                          |
| `colors`      | `list[str]`   | `["black", "white"]`                                             |
| `brand`       | `str \| None` | `"Levi's"` or `null`                                             |
| `platform`    | `str`         | `"depop"`, `"thredUp"`, or `"poshmark"`                          |

Failure case: Returns an empty list `[]` if nothing matches — never raises an exception.

**Internals:**

1. Loads all 40 listings via `load_listings()`.
2. Filters by `max_price` (inclusive) and `size` (case-insensitive substring).
3. Tokenizes `description` into lowercase keywords, scores each remaining listing by counting keyword hits in the listing's `title`, `description`, and `style_tags` (concatenated).
4. Drops listings with score 0 (no keyword overlap).
5. Sorts by score descending and returns the listing dicts.

---

### Tool 2: `suggest_outfit`

|             |                                                                                                                                                          |
| ----------- | -------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Purpose** | Generate outfit suggestions for a thrifted item, using the user's wardrobe when available or offering general styling advice when the wardrobe is empty. |
| **File**    | [tools.py](tools.py#L110-L191)                                                                                                                           |

**Inputs:**

| Parameter  | Type   | Description                                                                                                                                                                                   |
| ---------- | ------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `new_item` | `dict` | A listing dict (the item the user is considering). Reads `title`, `category`, `colors`, `style_tags`, `price`, and `platform`.                                                                |
| `wardrobe` | `dict` | A dict with an `items` key containing a list of wardrobe item dicts. Each wardrobe item has `name`, `category`, `colors`, `style_tags`, and optional `notes`. May be empty (`{"items": []}`). |

**Output:** `str` — a non-empty paragraph (2–5 sentences) of outfit advice.

- **Wardrobe has items:** suggests 1–2 specific outfit combinations pairing the new item with named pieces from the wardrobe. Example: _"Pair the Vintage Band Tee with your baggy straight-leg jeans for a relaxed 90s-grunge silhouette. Layer with the vintage black denim jacket and finish with the chunky white sneakers."_
- **Wardrobe is empty:** offers general styling advice — what kinds of items pair well, what aesthetic it suits, what occasions it's great for. Does NOT invent specific wardrobe pieces.

**Internals:**

1. Formats the `new_item` into a summary string (title, category, colors, style tags, price, platform).
2. Checks `wardrobe["items"]` — if empty, builds a general-styling prompt; otherwise formats every wardrobe piece into a bullet list and builds a specific-outfit prompt.
3. Calls Groq (`llama-3.3-70b-versatile`) with the prompt.
4. Returns the LLM response. If the LLM call fails (API error, network issue), returns a hardcoded fallback: _"Try pairing this with your favorite jeans and sneakers for an easy everyday look."_

---

### Tool 3: `create_fit_card`

|             |                                                                                        |
| ----------- | -------------------------------------------------------------------------------------- |
| **Purpose** | Generate a short, shareable Instagram/TikTok-style OOTD caption for the thrifted find. |
| **File**    | [tools.py](tools.py#L196-L258)                                                         |

**Inputs:**

| Parameter  | Type   | Description                                                                                   |
| ---------- | ------ | --------------------------------------------------------------------------------------------- |
| `outfit`   | `str`  | The outfit suggestion string from `suggest_outfit()`.                                         |
| `new_item` | `dict` | The listing dict for the thrifted item. Reads `title`, `price`, `platform`, and `style_tags`. |

**Output:** `str` — a 2–4 sentence caption that:

- Feels casual and authentic (like a real OOTD post, not a product listing)
- Mentions the item name, price, and platform naturally, once each
- Describes the outfit vibe in specific terms
- Varies across runs (LLM called with `temperature=1.0`)

Example: _"Found this vintage Smiths tour tee on depop for $22 and it's everything. Styled it with baggy jeans and chunky sneakers for that effortless 90s grunge energy. OOTD sorted. 🖤"_

**Internals:**

1. Guards against an empty or whitespace-only `outfit` string — returns `"Couldn't generate a fit card — the outfit suggestion was empty."` without calling the LLM.
2. Extracts `title`, `price`, `platform`, and `style_tags` from `new_item`.
3. Builds a prompt with the item details, outfit text, and caption-writing guidelines.
4. Calls Groq (`llama-3.3-70b-versatile`, `temperature=1.0`).
5. Returns the LLM response. If the LLM call fails, returns a fallback caption built from the item fields and outfit text.

---

## Planning Loop

The planning loop in [`run_agent()`](agent.py#L199-L284) follows a fixed 7-step sequence (full design documented in [planning.md](planning.md)):

```
User query + wardrobe
        │
        ▼
┌─────────────────────────────────┐
│ Step 1: Init session            │
│ _new_session(query, wardrobe)   │
└──────────────┬──────────────────┘
               ▼
┌─────────────────────────────────┐
│ Step 2: Parse query             │
│ _parse_query(query) → parsed    │
│ {description, size, max_price}  │
└──────────────┬──────────────────┘
               ▼
┌─────────────────────────────────┐
│ Step 3: Search listings         │
│ search_listings(desc, size, $)  │
└──────┬──────────────────┬───────┘
       │                  │
   results found      results empty
       │                  │
       ▼                  ▼
┌──────────────┐   ┌──────────────────────┐
│ Step 4: Pick │   │ EARLY EXIT            │
│ top result   │   │ session["error"] set  │
│ results[0]   │   │ return session        │
└──────┬───────┘   └──────────────────────┘
       ▼
┌─────────────────────────────────┐
│ Step 5: Suggest outfit          │
│ suggest_outfit(item, wardrobe)  │
│ (handles empty wardrobe inside) │
└──────────────┬──────────────────┘
               ▼
┌─────────────────────────────────┐
│ Step 6: Create fit card         │
│ create_fit_card(outfit, item)   │
│ (guards empty outfit inside)    │
└──────────────┬──────────────────┘
               ▼
┌─────────────────────────────────┐
│ Step 7: Return session          │
│ {parsed, search_results,        │
│  selected_item, outfit,         │
│  fit_card, error}               │
└─────────────────────────────────┘
```

**The only branch the agent loop itself makes** is at Step 3: if `search_listings` returns an empty list, the agent sets `session["error"]` and returns immediately — `suggest_outfit` and `create_fit_card` are never called with empty input. Every other decision (empty wardrobe, empty outfit string) is handled inside the tool that encounters it, so the pipeline always reaches the return statement.
That having been said, inside the tools, there is often error handling, such as if there are no listings -- a generic but helpful message is usually returned.

### Decision Ownership Table

| #   | Decision                      | Who checks it                | If true                     | If false                              |
| --- | ----------------------------- | ---------------------------- | --------------------------- | ------------------------------------- |
| 3   | `search_results` is empty?    | **Agent loop**               | Set `error`, return early   | Continue to step 4                    |
| 5   | `wardrobe["items"]` is empty? | **Inside `suggest_outfit`**  | General styling advice      | Specific outfits with wardrobe pieces |
| 6   | `outfit` string is empty?     | **Inside `create_fit_card`** | Return error message string | Call LLM for caption                  |

---

## State Management

All state for a single user interaction lives in **one `session` dict**, created by `_new_session()` and threaded through every step of `run_agent()`. There are no globals and no hidden state — each step reads the fields it needs from `session` and writes its result back, so the dict is both the single source of truth and the complete record of what happened.

### Session Fields

| Field               | Set by                     | Type           | Purpose                                                              |
| ------------------- | -------------------------- | -------------- | -------------------------------------------------------------------- |
| `query`             | `_new_session`             | `str`          | The original, unmodified user request                                |
| `parsed`            | Step 2 (`_parse_query`)    | `dict`         | `{"description", "size", "max_price"}` — inputs to `search_listings` |
| `search_results`    | Step 3 (`search_listings`) | `list[dict]`   | All matching listings, best match first                              |
| `selected_item`     | Step 4                     | `dict \| None` | `search_results[0]` — fed into both LLM tools                        |
| `wardrobe`          | `_new_session`             | `dict`         | The user's wardrobe (`{"items": [...]}`)                             |
| `outfit_suggestion` | Step 5 (`suggest_outfit`)  | `str \| None`  | Outfit advice; becomes the `outfit` argument to `create_fit_card`    |
| `fit_card`          | Step 6 (`create_fit_card`) | `str \| None`  | The shareable caption                                                |
| `error`             | Step 3 (on empty results)  | `str \| None`  | Set only on early exit; `None` on the success path                   |

### Data Flow

```
parsed → search_listings → search_results → selected_item
                                                    ├→ suggest_outfit → outfit_suggestion
                                                    └────────────────→ create_fit_card → fit_card
```

The `selected_item` dict is reused as the `new_item` argument for both LLM tools, and `wardrobe` is read directly from the session rather than passed around separately. The caller (Gradio UI or CLI test) checks `session["error"]` first — if it is not `None`, the interaction ended early and `outfit_suggestion` / `fit_card` remain `None`.

---

## Query Parsing

The query parser ([`_parse_query()`](agent.py#L87-L120)) uses a **dual-strategy approach**:

1. **Primary: LLM-based parsing** — Sends the raw query to Groq (`llama-3.3-70b-versatile`, `temperature=0.0`) with a structured few-shot prompt that instructs the model to return JSON with `description`, `size`, and `max_price`. The LLM handles all the edge cases that tripped up the original regex parser: canonicalizing `"size medium"` → `"M"`, extracting `"size extra small"` → `"XS"` as a multi-word phrase, and understanding prices without `$` signs (`"30 dollars"` → `30`).

2. **Fallback: regex parser** ([`_parse_query_regex()`](agent.py#L123-L170)) — If the LLM call fails for any reason (missing API key, network error, malformed JSON), the system automatically falls back to a deterministic regex parser that uses a strip-as-you-go strategy: extract price → remove from text → extract size → remove → use remainder as description keywords.

The function signature and return type are unchanged from the original design:

```python
def _parse_query(query: str) -> dict:
    """Returns {"description": str, "size": str | None, "max_price": float | None}."""
```

---

## Error Handling

Every failure mode is handled — nothing propagates as an uncaught exception to the user.

### Tool: `search_listings`

| Failure mode                | What the tool does                         | What the agent does                                                                                                                                                                                                                                                                                               | What the user sees                                                                                                                 |
| --------------------------- | ------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| No listings match the query | Returns `[]` (empty list). Does not raise. | Checks `if not session["search_results"]:` after the call. Sets `session["error"]` to a message like `"Sorry — no listings matched 'vintage graphic tee' under $30. Try a broader description or a higher budget."` and returns the session immediately. `suggest_outfit` and `create_fit_card` are never called. | The Gradio UI shows the error message in the first panel. The other two panels are blank. The error includes a concrete next step. |

**Concrete example:**

```
Query: "designer ballgown size XXS under $5"
Parsed: {"description": "designer ballgown", "size": "XXS", "max_price": 5.0}
Result: 0 listings match (no ballgowns in the dataset at ≤$5)
Error:  "Sorry — no listings matched 'designer ballgown' under $5.
        Try a broader description or a higher budget."
```

### Tool: `suggest_outfit`

| Failure mode                                  | What the tool does                                                                                                                                                                                                                | What the agent does                                                                    | What the user sees                                                                                                        |
| --------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------- |
| Wardrobe is empty (`wardrobe["items"] == []`) | Detects the empty list. Instead of erroring, builds a different LLM prompt: _"The user doesn't have any wardrobe items saved yet. Suggest general pairings and vibes..."_ Returns a non-empty string with general styling advice. | Does not branch. Stores whatever string comes back and passes it to `create_fit_card`. | The outfit panel shows general styling advice (no specific wardrobe piece names mentioned). The fit card still generates. |
| LLM call fails (API error, network, timeout)  | Catches the exception and returns the hardcoded fallback: _"Try pairing this with your favorite jeans and sneakers for an easy everyday look."_                                                                                   | Does not branch. Stores the fallback string and continues.                             | The outfit panel shows the fallback advice.                                                                               |

**Concrete example (empty wardrobe):**

```
Query: "graphic tee under $30"
Wardrobe: Empty (no items)
Outfit:  "A graphic tee pairs well with relaxed-fit denim, wide-leg trousers,
         or even a slip skirt for contrast. Chunky sneakers or platform boots
         complete the look, and a crossbody bag adds a practical touch. This
         piece works for casual days, coffee runs, or weekend hangs."
```

### Tool: `create_fit_card`

| Failure mode                                 | What the tool does                                                                                                                                                              | What the agent does                                 | What the user sees                                                                        |
| -------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------- | ----------------------------------------------------------------------------------------- |
| `outfit` string is empty or whitespace-only  | Checks `if not outfit or not outfit.strip():` at the top. Returns `"Couldn't generate a fit card — the outfit suggestion was empty."` immediately — no LLM call, no exception.  | Does not branch. Stores whatever string comes back. | The fit card panel shows the error message. The listing and outfit panels are unaffected. |
| LLM call fails (API error, network, timeout) | Catches the exception and returns a fallback caption built from the item fields and outfit text: `"Found this {title} on {platform} for ${price} and had to grab it. {outfit}"` | Does not branch. Stores the fallback string.        | The fit card panel shows the fallback caption.                                            |

**Concrete example (LLM fallback):**

```
Input:  outfit = "...", item = {"title": "Vintage Band Tee", "price": 22.0, "platform": "depop"}
Output: "Found this Vintage Band Tee on depop for $22.0 and had to grab it.
         Pair the Vintage Band Tee with your baggy straight-leg jeans..."
```

### Query Parsing (`_parse_query`)

| Failure mode                                              | What the parser does                                                 | What the agent does                                                |
| --------------------------------------------------------- | -------------------------------------------------------------------- | ------------------------------------------------------------------ |
| LLM call fails (missing API key, network error, bad JSON) | Catches the exception and falls back to `_parse_query_regex(query)`. | Unaware of the fallback — receives the same dict shape either way. |
| LLM returns malformed JSON                                | Caught by `json.loads()` → exception → falls back to regex parser.   | Same as above.                                                     |

---

## Spec Reflection

### What the original spec called for

The planning document ([planning.md](planning.md)) specified:

- Three tools: `search_listings`, `suggest_outfit`, `create_fit_card` — each independently callable and testable
- A planning loop in `run_agent()` that wires the tools together in a fixed sequence with one conditional branch (empty search results → early exit)
- State managed through a single `session` dict threaded through every step
- Error handling at every failure point, with the agent loop itself only branching on empty search results
- A Gradio interface in `app.py` with three output panels (listing, outfit, fit card)

### How the implementation matches

| Spec requirement              | Implementation                                                                               | Status     |
| ----------------------------- | -------------------------------------------------------------------------------------------- | ---------- |
| Three standalone tools        | All three implemented in [tools.py](tools.py) with the exact signatures from the spec        | ✅ Matches |
| Planning loop with one branch | `run_agent()` follows the 7-step sequence; only branches on empty `search_results`           | ✅ Matches |
| Session dict state management | `_new_session()` initializes all 8 fields; each step reads/writes to `session`               | ✅ Matches |
| Error handling per tool       | Every tool handles its failure mode internally (see [Error Handling](#error-handling) above) | ✅ Matches |
| Gradio interface              | `app.py` with three output panels, example queries, and wardrobe selection                   | ✅ Matches |

### Where the implementation diverges from the original spec

1. **Query parsing: regex → LLM with fallback.** The planning doc originally described a pure-regex parser and gave regex as the chosen approach. After discovering that the regex parser mishandled common query patterns (`"size medium"` not canonicalized, `"size extra small"` truncated, no price extraction without `$`), the parser was upgraded to an LLM-based primary with the original regex preserved as a fallback. The function signature and return type are unchanged, so no downstream code needed modification. This is documented in the updated [planning.md](planning.md) "Chosen approach" section.

2. **Two parser functions instead of one.** The original spec assumed a single `_parse_query()` function. The implementation now has `_parse_query()` (LLM) and `_parse_query_regex()` (fallback), but the public interface — `run_agent()` calling `_parse_query(query)` — is identical.

### What the spec didn't anticipate (but the implementation handles)

- **Phrase order variation:** Because the LLM parser understands semantics rather than regex match order, queries like `"size M, under $30, vintage graphic tee"` and `"vintage graphic tee size M under $30"` produce identical parsed output.
- **Price without `$`:** `"30 dollars"`, `"max 50"`, `"cheaper than 25"` all correctly extract `max_price` via the LLM path.
- **Multi-word size after "size":** `"size extra small"` correctly maps to `"XS"` via the LLM path (the regex fallback would only capture `"extra"`).
- **LLM unavailability:** If the Groq API is unreachable or the key is missing, the regex fallback ensures the agent still functions — it degrades to the regex parser's capabilities rather than failing entirely.
- **Markdown-wrapped JSON responses:** The LLM parser strips ` `json```fences if the model wraps its output, preventing`json.loads()` failures.

### Design trade-offs

| Trade-off                                  | Decision                                                    | Rationale                                                                                                                                                  |
| ------------------------------------------ | ----------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------- |
| LLM latency vs. regex speed                | Accept ~500ms LLM call per query                            | The correctness gains (canonical sizes, robust price extraction) outweigh the latency cost. The prompt uses `temperature=0.0` for deterministic caching.   |
| Two parsers vs. one                        | Keep both, LLM primary                                      | The regex fallback costs nothing (no API call, instant) and provides resilience. Code duplication is minimal (30 lines).                                   |
| Agent branches vs. tool-internal guards    | Agent only branches on empty search; tools guard themselves | Keeps the planning loop simple (one branch). Each tool owns its edge cases — the agent doesn't need to know about empty wardrobes or empty outfit strings. |
| Hardcoded fallbacks vs. raising exceptions | Every LLM-dependent tool has a hardcoded fallback string    | Ensures the user always sees _something_ even during API outages. The fallbacks are generic but serviceable.                                               |

---

## AI Usage

This project was built with significant AI assistance. Below are some specific instances — what was given to the AI, what it produced, and what was overridden or changed before the code was accepted.

### Instance 1: Tool Implementation — `suggest_outfit` and `create_fit_card`

**What I gave the AI ([planning.md § Tool 2](planning.md#tool-2-suggest_outfit) and [§ Tool 3](planning.md#tool-3-create_fit_card)):**

- The **Tool 2 and Tool 3 spec blocks** — full input/output descriptions, the wardrobe-present vs. wardrobe-empty branching logic, the caption style guidelines, and the `temperature=1.0` note for `create_fit_card`
- The **Error Handling table** rows for both tools — empty wardrobe → general styling, empty outfit → error message string, LLM failure → hardcoded fallback
- The **`_get_groq_client()` helper** already in [tools.py](tools.py#L27-L34) — the AI was told to use it for LLM calls
- The **wardrobe schema** from [data/wardrobe_schema.json](data/wardrobe_schema.json) — field definitions for each wardrobe item (`name`, `category`, `colors`, `style_tags`, `notes`)

**What the AI produced:**

A working `suggest_outfit()` ([tools.py:110-191](tools.py#L110-L191)) that formats items into prompts, branches on empty wardrobe, calls Groq, and returns the LLM response. A working `create_fit_card()` ([tools.py:196-258](tools.py#L196-L258)) that guards against empty outfit input, builds a caption prompt with item details, calls Groq with `temperature=1.0`, and returns the caption.

**What I changed or overrode:**

- **`suggest_outfit` fallback string** — the AI initially used a generic fallback. I revised it to `"Try pairing this with your favorite jeans and sneakers for an easy everyday look."` to sound more natural and on-brand for a fashion app.
- **`suggest_outfit` dict** — the ordering of the elemnts in the dict being updated and passed was initially inconsistent across functions; I standardized it for cleanliness.
- **`create_fit_card` fallback string** — the AI returned a static message on LLM failure. I changed it to a template that still includes the item's title, platform, and price so the user gets _something_ useful rather than a generic error: `f"Found this {title} on {platform} for ${price} and had to grab it. {outfit}"`

---

### Instance 2: Query Parser — Two AI Passes with a Human Pivot

This feature took two AI passes, with a human-directed architectural change in between.

**Pass 1 — What I gave the AI:**

- The **starter code skeleton** — `_new_session()` was stubbed out, `run_agent()` had only TODO comments describing the 7 steps (including _"Step 2: Parse the user's query to extract a description, size, and max_price. You can use regex, string splitting, or ask the LLM to parse it — document your choice in planning.md"_). No `_parse_query()` function existed yet.
- The **Planning Loop section** of [planning.md](planning.md) — the description of what `parsed` should contain (`description`, `size`, `max_price`) and the note that regex or LLM were both valid approaches.
- The instruction to implement the 7-step loop, choosing whichever parsing method made sense.

**Pass 1 — What the AI produced:**

The AI created a **regex-based `_parse_query()`** — the original function with `_FILLER` (a set of ~30 filler words to strip), `_WORD_SIZES` (mapping `"small"`→`"S"`, `"medium"`→`"M"`, `"extra large"`→`"XL"`), and a strip-as-you-go extraction strategy: match and remove price → match and remove size → use remaining tokens as description keywords.

**My override between passes — the pivot:**

After testing the regex parser, I found three concrete failure cases:

- `"size medium graphic tee"` — the regex `\bsize\s+([A-Za-z0-9/]+)` captured `"medium"` as a raw string without canonicalizing it to `"M"`. `search_listings` then did a substring check (`"medium" in listing["size"]`) which never matched any listing (all sizes are `"M"`, `"S/M"`, etc.) → **zero results**.
- `"size extra small yoga pants"` — the same regex only captured `"extra"` (one token), and the word-based fallback couldn't recover because `"extra"` had already been stripped from the text → degraded to `"S"`.
- `"30 dollars"` — the bare-price regex required a `$` sign, so prices expressed as `"30 dollars"` or `"30 bucks"` were silently dropped.

I directed the AI: **"Change `_parse_query` to an LLM-based parser. The job of the function should remain the same."**

**Pass 2 — What the AI produced (from my instruction):**

A new dual-parser architecture ([agent.py:87-170](agent.py#L87-L170)):

- `_parse_query()` (primary) — sends the raw query to Groq with a structured few-shot prompt, parses the JSON response, returns the structured dict
- `_parse_query_regex()` (fallback) — the original regex function, preserved verbatim and called automatically if the LLM path fails for any reason

**What I changed or overrode after Pass 2:**

- **Updated [planning.md](planning.md)** — after the code change, I updated the "Chosen approach" section in planning.md from "regex" to "LLM with regex fallback" with a justification for the switch and documentation of the new architecture.

---

### Patterns That Worked Well

- **Giving the AI the full spec, not just a prompt.** The tool implementations came out correct on the first try because the AI had the complete Tool 1/2/3 blocks from planning.md — inputs, outputs, edge cases, failure modes, and expected behavior — rather than a vague "write a search function."
- **Keeping the TODO docstrings in the starter code.** The stubbed function signatures with numbered implementation steps gave the AI a scaffold to fill in. The AI produced code that followed the TODO list exactly.
- **Few-shot examples in LLM prompts.** The query parser prompt needed 7 diverse examples before the model consistently handled edge cases like `"size extra small"` and `"30 dollars"`. Fewer examples led to inconsistent JSON or missed canonicalization.

### Patterns to Improve

- **Iterating LLM prompts through the same AI tool.** Refining the query parser prompt took several rounds because each iteration could only test one version at a time. A better workflow would be to give the AI a set of test queries and ask it to self-critique its own prompt against failures.
- **Fallback strings should be designed up front.** The `suggest_outfit` and `create_fit_card` fallback strings were afterthoughts — I only noticed they were too generic when I actually hit an API failure in testing. Specifying fallback copy in the planning doc would have avoided the revision.

---

## The Mock Listings Dataset

`data/listings.json` contains 40 mock secondhand listings across five categories (tops, bottoms, outerwear, shoes, accessories) and multiple styles (vintage, y2k, grunge, cottagecore, streetwear, and more).

Each listing has: `id`, `title`, `description`, `category`, `style_tags`, `size`, `condition`, `price`, `colors`, `brand`, and `platform`.

Load it with:

```python
from utils.data_loader import load_listings
listings = load_listings()
```

## The Wardrobe Schema

`data/wardrobe_schema.json` defines the format for a user's existing wardrobe:

- `schema`: field definitions for a wardrobe item (`name`, `category`, `colors`, `style_tags`, `notes`)
- `example_wardrobe`: a sample wardrobe with 10 items for testing
- `empty_wardrobe`: a starting template for a new user (`{"items": []}`)

Load wardrobes with:

```python
from utils.data_loader import get_example_wardrobe, get_empty_wardrobe

wardrobe = get_example_wardrobe()   # 10 items
wardrobe = get_empty_wardrobe()     # 0 items
```
