# FitFindr — planning.md

> Complete this document before writing any implementation code.
> Your spec and agent diagram are what you'll use to direct AI tools (Claude, Copilot, etc.) to generate your implementation — the more specific they are, the more useful the generated code will be.
> Your planning.md will be reviewed as part of your submission.
> Update it before starting any stretch features.

---

## Tools

List every tool your agent will use. For each tool, fill in all four fields.
You must have at least 3 tools. The three required tools are listed — add any additional tools below them.

### Tool 1: search_listings

**What it does:**
<!-- Describe what this tool does in 1–2 sentences -->

**Input parameters:**
<!-- List each parameter, its type, and what it represents -->
- `description` (str): ...
- `size` (str): ...
- `max_price` (float): ...

**What it returns:**
<!-- Describe the return value — what fields does a result contain? -->

**What happens if it fails or returns nothing:**
<!-- What should the agent do if no listings match? -->

---

### Tool 2: suggest_outfit

**What it does:**
<!-- Describe what this tool does in 1–2 sentences -->

**Input parameters:**
<!-- List each parameter, its type, and what it represents -->
- `new_item` (dict): ...
- `wardrobe` (dict): ...

**What it returns:**
<!-- Describe the return value -->

**What happens if it fails or returns nothing:**
<!-- What should the agent do if the wardrobe is empty or no outfit can be suggested? -->

---

### Tool 3: create_fit_card

**What it does:**
<!-- Describe what this tool does in 1–2 sentences -->

**Input parameters:**
<!-- List each parameter, its type, and what it represents -->
- `outfit` (...): ...

**What it returns:**
<!-- Describe the return value -->

**What happens if it fails or returns nothing:**
<!-- What should the agent do if the outfit data is incomplete? -->

---

### Additional Tools (if any)

<!-- Copy the block above for any tools beyond the required three -->

---

## Planning Loop

**How does your agent decide which tool to call next?**
<!-- Describe the logic your planning loop uses. What does it look at? What conditions change its behavior? How does it know when it's done? -->

---

## State Management

**How does information from one tool get passed to the next?**
<!-- Describe how your agent stores and accesses state within a session. What data is tracked? How is it passed between tool calls? -->

---

## Error Handling

For each tool, describe the specific failure mode you're handling and what the agent does in response.

| Tool | Failure mode | Agent response |
|------|-------------|----------------|
| search_listings | No results match the query | |
| suggest_outfit | Wardrobe is empty | |
| create_fit_card | Outfit input is missing or incomplete | |

---

## Architecture

<!-- Draw a diagram of your agent showing how the components connect:
     User input → Planning Loop → Tools (search_listings, suggest_outfit, create_fit_card)
                                                                          ↕
                                                                   State / Session
     Show what triggers each tool, how state flows between them, and where error paths branch off.
     ASCII art, a Mermaid diagram (https://mermaid.js.org/syntax/flowchart.html), or an embedded
     sketch are all fine. You'll share this diagram with an AI tool when asking it to implement
     the planning loop and each individual tool. -->

---

## AI Tool Plan

<!-- For each part of the implementation below, describe:
     - Which AI tool you plan to use (Claude, Copilot, ChatGPT, etc.)
     - What you'll give it as input (which sections of this planning.md, your agent diagram)
     - What you expect it to produce
     - How you'll verify the output matches your spec before moving on

     "I'll use AI to help me code" is not a plan.
     "I'll give Claude my Tool 1 spec (inputs, return value, failure mode) and ask it to implement
     search_listings() using load_listings() from the data loader — then test it against 3 queries
     before trusting it" is a plan. -->

**Milestone 3 — Individual tool implementations:**

**Milestone 4 — Planning loop and state management:**

---

## A Complete Interaction (Step by Step)

FitFindr is a secondhand-shopping assistant that takes a user's natural-language query, searches a marketplace of thrifted clothing listings, and returns a complete styling recommendation. The agent parses the user's request to extract what they're looking for, then calls `search_listings` to find matching items — if nothing matches, it stops and tells the user so. When results are found, it picks the best match and feeds it into `suggest_outfit` to generate outfit ideas (using the user's existing wardrobe when available, or offering general styling advice when the wardrobe is empty), then wraps everything into a social-media-style fit card via `create_fit_card` so the user walks away with a concrete, shareable OOTD.

**Example user query:** "I'm looking for a vintage graphic tee under $30. I mostly wear baggy jeans and chunky sneakers. What's out there and how would I style it?"

**Step 1 — Parse the query:**
The agent extracts structured parameters from the natural-language input: `description = "vintage graphic tee"`, `size = None` (no size mentioned), `max_price = 30.0`. It stores these in `session["parsed"]`.

**Step 2 — Search listings:**
The agent calls `search_listings(description="vintage graphic tee", size=None, max_price=30.0)`. The tool loads all 40 listings, filters to those priced ≤ $30, scores each by keyword overlap against the description ("vintage", "graphic", "tee"), drops zero-score items, and sorts by relevance descending. It returns, say, 3 matches — a vintage band tee ($22, depop), a retro graphic tee ($18, poshmark), and a washed logo tee ($25, thredUp). **Failure path:** if zero results match, the tool returns `[]`, and the agent sets `session["error"]` to a message like "No listings matched 'vintage graphic tee' under $30" and returns immediately — no further tools are called.

**Step 3 — Select top item:**
The agent picks the highest-scored result (the vintage band tee, $22 from depop) and stores it as `session["selected_item"]`.

**Step 4 — Suggest outfit:**
The agent calls `suggest_outfit(new_item=selected_item, wardrobe=user_wardrobe)`. Since the wardrobe contains baggy jeans and chunky sneakers, the tool builds an LLM prompt listing those pieces alongside the vintage band tee and asks for specific outfit combinations. It returns a string like: "Pair the vintage band tee with your baggy jeans for a relaxed 90s-grunge silhouette, then ground the look with your chunky sneakers for a streetwear edge." **Failure path:** if the wardrobe were empty, the tool would instead ask the LLM for general styling advice (what pairs well with a vintage graphic tee, what vibe it suits) rather than erroring out.

**Step 5 — Create fit card:**
The agent calls `create_fit_card(outfit=outfit_suggestion, new_item=selected_item)`. The tool first checks that `outfit` is non-empty, then builds an LLM prompt with the item details (title, $22, depop) and the outfit text. It generates a 2-4 sentence Instagram/TikTok-style caption like: "Found this vintage band tee on depop for $22 and it's giving everything. Styled it with my go-to baggy jeans and chunky sneaks for that effortless 90s energy. OOTD sorted." **Failure path:** if `outfit` were empty or whitespace-only, `create_fit_card` returns an error message string instead of generating nonsense — no exception is raised.

**Final output to user:**
The Gradio UI displays three things: the matching listing card (the vintage band tee with its details), the outfit suggestion paragraph, and the fit card caption — giving the user a complete, shareable styling recommendation.
