---
name: run-fitfindr
description: Build, run, and smoke-test FitFindr. Use when asked to run the app, test it, start it, take a screenshot of the Gradio UI, or verify a change to tools/agent/pipeline.
---

FitFindr is a secondhand-fashion shopping assistant — a Python Gradio web app that
takes natural-language queries, searches 40 mock listings, and returns outfit
suggestions with shareable fit cards.

**Primary driver:** `python .claude/skills/run-fitfindr/smoke_test.py` —
imports `run_agent()` and all three tools directly, runs 33 checks across the
full pipeline. Drive the Gradio UI via its HTTP SSE API (no browser needed).

All paths below are relative to the repo root.

## Prerequisites

- Python 3.12+ with a venv at `.venv/`
- Groq API key (free — get one at https://console.groq.com)

```bash
# If you need to create the venv:
python -m venv .venv
```

No system packages are required — this is a pure-Python project.

## Setup

```bash
.venv/Scripts/pip install -r requirements.txt
```

Set your API key:

```bash
# In .env at the repo root:
echo 'GROQ_API_KEY=gsk_...' > .env
```

## Run (agent path) — smoke test

The smoke test exercises every layer a PR might touch: individual tools, query
parsing, and the full agent loop (happy path, no-results, empty wardrobe).

```bash
.venv/Scripts/python .claude/skills/run-fitfindr/smoke_test.py
```

Expected output: `All 33 tests passed!` with exit code 0.

The smoke test runs these groups:

| group | what it covers |
|---|---|
| Prerequisites | API key set, listings load (40 items), wardrobe loads (10 items) |
| Tool 1: `search_listings` | keyword search, price filter, no-results empty list |
| Tool 2: `suggest_outfit` | with wardrobe, empty wardrobe (general styling, no invented items) |
| Tool 3: `create_fit_card` | happy path, empty-outfit guard, whitespace-outfit guard |
| Query parsing | description/size/price extraction, nulls when absent |
| Agent loop | happy path (example wardrobe), empty wardrobe, no-results early exit |

### Direct invocation for single queries

When debugging one tool or query, import directly instead of running
the full suite:

```python
.venv/Scripts/python -c "
from agent import run_agent
from utils.data_loader import get_example_wardrobe

s = run_agent('vintage graphic tee under \$30', get_example_wardrobe())
print('Error:', s['error'])
print('Item:', s['selected_item']['title'] if s['selected_item'] else None)
print('Outfit:', s['outfit_suggestion'][:200] if s['outfit_suggestion'] else None)
print('Fit card:', s['fit_card'][:200] if s['fit_card'] else None)
"
```

## Run (agent path) — Gradio UI

The Gradio app exposes an SSE-based HTTP API on port 7860. No browser needed.

### Launch the server

```bash
.venv/Scripts/python app.py &
GRADIO_PID=$!
timeout 15 bash -c 'until curl -sf http://localhost:7860 >/dev/null; do sleep 0.5; done'
```

On Windows (PowerShell):

```powershell
$proc = Start-Process .venv\Scripts\python.exe -ArgumentList app.py -PassThru
```

### Call the API

Gradio 6.x uses event-driven SSE. Two steps: POST to trigger, then GET the
event stream.

```bash
# Step 1 — trigger the query, get an event_id
curl -sf -X POST http://localhost:7860/gradio_api/call/handle_query \
  -H 'Content-Type: application/json' \
  -d '{"data":["vintage graphic tee under $30","Example wardrobe"]}' \
  | python -c "import sys,json; print(json.load(sys.stdin)['event_id'])"

# Step 2 — stream the result (replace <event_id> from step 1)
curl -sf http://localhost:7860/gradio_api/call/handle_query/<event_id>
```

The SSE response contains `event: complete` followed by `data: [...]` — a
JSON array of three strings: `[listing_text, outfit_suggestion, fit_card]`.

### Stop

```bash
kill $GRADIO_PID
# or: pkill -f 'python app.py'
```

## Run (human path)

```bash
.venv/Scripts/python app.py
# → Opens Gradio UI at http://localhost:7860
# Stop with Ctrl-C
```

For a CLI quick-test (no Gradio UI):

```bash
.venv/Scripts/python agent.py
# → Runs two end-to-end queries: a happy-path and a no-results test
```

## Test

No pytest suite exists in this project. The smoke test (`smoke_test.py`) is the
test harness.

## Gotchas

- **Gradio API uses SSE (not REST).** A POST to `/gradio_api/call/<endpoint>`
  returns just an `event_id`. You MUST make a second GET to
  `/gradio_api/call/<endpoint>/<event_id>` to stream the actual result.
  Raw `curl -X POST ...` will appear to succeed but return only an ID.
- **`GROQ_API_KEY` must be in `.env` at the repo root.** `tools.py` and
  `agent.py` both call `load_dotenv()` at import time. Exporting the env var
  in the shell also works, but the `.env` file is the canonical location.
- **The smoke test makes LLM calls.** Each run hits the Groq API for query
  parsing (5 calls) and LLM tools (6 calls). The query-parser prompt uses
  `temperature=0.0` which gives deterministic responses for caching.
- **Size matching is substring-based.** `search_listings(size="M")` matches
  listings with size `"S/M"`, `"M/L"`, and `"M"`. This is by design — the mock
  dataset has mixed size formats.
- **Empty wardrobe does NOT error.** `suggest_outfit()` detects an empty
  `wardrobe["items"]` list and returns general styling advice instead of
  specific outfit combinations. This is not a bug.

## Troubleshooting

- **`ModuleNotFoundError: No module named 'groq'`** — dependencies not
  installed. Run `.venv/Scripts/pip install -r requirements.txt`.
- **`ValueError: GROQ_API_KEY not set`** — the `.env` file is missing or
  doesn't contain `GROQ_API_KEY`. Create `.env` in the repo root with
  `GROQ_API_KEY=your_key_here`.
- **`ConnectionRefusedError` on port 7860** — Gradio server is already
  running or port is in use. Run `pkill -f 'python app.py'` first.
- **Gradio API returns 404 on `/info`** — Gradio 6.x moved the API to
  `/gradio_api/info`. Use that path instead.
- **Smoke test fails on query parsing checks** — the LLM (llama-3.3-70b)
  returned an unexpected parse. This happens rarely with `temperature=0.0`.
  Re-run; if persistent, the Groq model may have changed behavior.
