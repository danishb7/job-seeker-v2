Job Seeker (NVIDIA NIM + Tavily) — From-Scratch Build Plan

This plan reproduces the existing app exactly, but on a free LLM backend, with token-saving choices baked in from day one. Build inside a fresh empty repo.



1. Stack & rationale





Backend: Python 3.11+, FastAPI, Uvicorn (matches current architecture).



LLM: NVIDIA NIM via OpenAI-compatible endpoint





Base URL: https://integrate.api.nvidia.com/v1



Default model: deepseek-ai/deepseek-v3 (free, strong tool-calling + JSON).



Web search: Tavily (tavily-python), free tier ~1000 calls/month, returns clean ranked snippets perfect for LLMs.



Why this combo: NVIDIA NIM has no built-in browser. We expose Tavily to the model via OpenAI-style function calling, run a small tool-calling loop, and ask the model to emit a strict JSON object via response_format={"type": "json_schema", ...} (DeepSeek-V3 supports this through the NIM gateway).

Token-saving optimizations (your numbered list 2–8) are mapped to concrete steps below.



2. Final repository layout

job-seeker/
  run.bat                        # Windows double-click launcher
  run.command                    # macOS double-click launcher (chmod +x)
  run_server.py                  # picks free port on 127.0.0.1, prints URL
  requirements.txt
  .env.example
  .gitignore
  README.md
  job_requirements.md            # seeded preferences
  results/                       # auto-created; CSV per run
  app/
    __init__.py
    main.py                      # FastAPI routes
    config.py                    # env + paths
    schemas.py                   # Pydantic models
    requirements_loader.py       # read/write + preamble stripping (opt #5)
    search_provider.py           # Tavily wrapper
    agent.py                     # NVIDIA NIM tool-calling loop + structured output
    csv_writer.py                # per-run CSV
    templates/
      index.html
    static/
      styles.css
      app.js
      favicon.svg
  tests/
    conftest.py
    test_config.py
    test_requirements_loader.py
    test_csv_writer.py
    test_agent.py                # mocks NIM + Tavily
    test_main.py
  .github/workflows/tests.yml    # pytest on push/PR



3. Dependencies (requirements.txt)

fastapi>=0.110
uvicorn[standard]>=0.27
openai>=1.50
tavily-python>=0.5
jinja2>=3.1
python-dotenv>=1.0
pydantic>=2.6
pytest>=8.0
httpx>=0.27

openai SDK is reused as a thin client because NVIDIA NIM is OpenAI-API-compatible.

4. Environment (.env.example)

NVIDIA_API_KEY=nvapi-...
NVIDIA_BASE_URL=https://integrate.api.nvidia.com/v1
NVIDIA_MODEL=deepseek-ai/deepseek-v3

TAVILY_API_KEY=tvly-...
TAVILY_SEARCH_DEPTH=basic
TAVILY_MAX_RESULTS=6
TAVILY_INCLUDE_DOMAINS=linkedin.com,indeed.com,idealist.org,higheredjobs.com

MAX_OUTPUT_TOKENS=4096       # opt #7 — far below the old 10240 cap
MAX_SEARCH_CALLS=2           # opt #2 — was 4 in old prompt
MAX_JOBS=10
WHY_MATCH_MAX_CHARS=100      # opt #8 — was 140
USER_LOCATION_HINT=Fort Mill, SC (Charlotte NC metro)

.gitignore excludes .env, .venv/, results/, __pycache__/, *.tmp.



5. Token-saving implementation map (opts 2–8)





Opt #2 — fewer searches: hard-cap the tool-loop iterations in agent.py at MAX_SEARCH_CALLS=2. After 2 Tavily calls the loop refuses further web_search tool calls and forces the model to emit final JSON.



Opt #3 — Structured Outputs: pass response_format={"type": "json_schema", "json_schema": {...}} on the final call. The schema definition lives in code (agent.JOB_SCHEMA), not in the prompt, so the schema text is never billed as input tokens. _extract_json regex/fence stripping is removed.



Opt #4 — trimmed system prompt: ~80 tokens. Final text:

  You find currently-open US job postings matching the user's preferences (Markdown).
  Rules:
  - Call web_search at most {MAX_SEARCH_CALLS} times; combine keywords per query.
  - Prefer LinkedIn, Indeed, Idealist, HigherEdJobs, university career pages.
  - Honor Must-Have / Exclude strictly.
  - Return up to {MAX_JOBS} matches, best-ranked first. Use null for unknown fields.
  - "why_match": one sentence, <= {WHY_MATCH_MAX_CHARS} chars.
  






Opt #5 — strip preamble: requirements_loader.read_for_agent() (a new helper, distinct from read_preferences() used by the UI) removes the leading > ... blockquote, blank/empty bullets like - Minimum: (leave blank if no requirement), and the H1 title before sending to the model. The raw file is still preserved for the UI editor.



Opt #6 — prompt-caching aware: the system prompt is a module-level constant built once at import. Static prefix → dynamic prefs ordering preserved (already good). Add a # DO NOT EDIT casually comment so future edits don't bust caching. Note in README that NVIDIA NIM may or may not honor prefix caching; this is best-effort.



Opt #7 — lower output cap: pass max_tokens=MAX_OUTPUT_TOKENS (4096) on every call.



Opt #8 — tighten per-row output: schema enforces why_match: maxLength=WHY_MATCH_MAX_CHARS. posted and is_nonprofit_or_h1b_cap_exempt remain (UI uses them) but the schema marks them as nullable so the model can skip rather than fabricate.



6. Agent design — app/agent.py

Tool-calling loop pseudocode:

client = OpenAI(api_key=NVIDIA_API_KEY, base_url=NVIDIA_BASE_URL)

TOOLS = [{
  "type": "function",
  "function": {
    "name": "web_search",
    "description": "Search the live web for job postings.",
    "parameters": {
      "type": "object",
      "properties": {"query": {"type": "string"}},
      "required": ["query"],
    },
  },
}]

def search_jobs(prefs_md_for_agent: str) -> list[dict]:
    msgs = [
      {"role": "system", "content": SYSTEM_PROMPT},
      {"role": "user", "content": f"USER PREFERENCES:\n\n{prefs_md_for_agent}"},
    ]
    searches_used = 0
    for _ in range(MAX_SEARCH_CALLS + 1):  # +1 for final JSON turn
        kwargs = dict(model=NVIDIA_MODEL, messages=msgs, max_tokens=MAX_OUTPUT_TOKENS)
        if searches_used < MAX_SEARCH_CALLS:
            kwargs["tools"] = TOOLS
        else:
            kwargs["response_format"] = {"type": "json_schema", "json_schema": JOB_SCHEMA}
        resp = client.chat.completions.create(**kwargs)
        msg = resp.choices[0].message
        if msg.tool_calls:
            for tc in msg.tool_calls:
                query = json.loads(tc.function.arguments)["query"]
                results = search_provider.tavily_search(query)
                msgs.append(msg.model_dump())
                msgs.append({"role": "tool", "tool_call_id": tc.id,
                             "name": "web_search", "content": json.dumps(results)})
                searches_used += 1
            continue
        return _normalise_jobs(json.loads(msg.content))
    return []

Retry logic: bare try/except on httpx.HTTPStatusError with 1 retry (NVIDIA's free tier rate-limits but doesn't return OpenAI-style "try again in Xs" hints; exponential backoff, 2 attempts max).

JOB_SCHEMA (lives in code, not in prompt):

JOB_SCHEMA = {
  "name": "JobList",
  "schema": {
    "type": "object",
    "properties": {
      "jobs": {
        "type": "array",
        "maxItems": MAX_JOBS,
        "items": {
          "type": "object",
          "properties": {
            "title": {"type": "string"},
            "company": {"type": "string"},
            "location": {"type": "string"},
            "work_mode": {"type": "string", "enum": ["Remote", "Hybrid", "On-site", ""]},
            "salary": {"type": ["string", "null"]},
            "is_nonprofit_or_h1b_cap_exempt": {"type": ["boolean", "null"]},
            "why_match": {"type": "string", "maxLength": WHY_MATCH_MAX_CHARS},
            "posted": {"type": ["string", "null"]},
            "url": {"type": "string"},
            "source": {"type": "string"},
          },
          "required": ["title", "company", "url"],
        },
      }
    },
    "required": ["jobs"],
  },
  "strict": True,
}

7. Search provider — app/search_provider.py

Thin wrapper around TavilyClient. Returns a compact list of dicts (title, url, snippet) — not the full Tavily response — to keep tool-message tokens minimal:

def tavily_search(query: str) -> list[dict]:
    raw = client.search(
        query=query,
        search_depth=TAVILY_SEARCH_DEPTH,         # "basic" is cheaper
        max_results=TAVILY_MAX_RESULTS,
        include_domains=TAVILY_INCLUDE_DOMAINS or None,
        topic="general",
    )
    return [
        {"title": r["title"], "url": r["url"], "snippet": r["content"][:400]}
        for r in raw.get("results", [])
    ]

Snippet truncation to 400 chars matters: it prevents a single search from dumping ~10k tokens of page text back into the conversation.

8. FastAPI surface — app/main.py

Identical to the current app's HTTP surface so the frontend is unchanged:





GET / → renders index.html with {model, preferences_path}.



GET /favicon.ico → 307 to /static/favicon.svg.



GET /api/preferences → {"content": "<raw md>"}.



PUT /api/preferences {content} → atomic write via requirements_loader.



POST /api/preferences/reload → re-read from disk.



POST /api/search → runs agent.search_jobs(prefs_for_agent), writes CSV, returns:

  {"jobs":[...], "csv_filename":"jobs_YYYYMMDD_HHMMSS.csv",
   "model":"deepseek-ai/deepseek-v3", "elapsed_seconds":12.3}
  






GET /api/results → {"results":[{filename, created_at, rows, size_bytes}, ...]}.



GET /api/results/{filename} → CSV download, with path-traversal guard (resolve, must live under RESULTS_DIR, must end in .csv).



GET /api/health → {"status":"ok","model":"..."}.

9. CSV writer — app/csv_writer.py

Identical columns and naming to today: title, company, type, location, salary, posting_date, link, source, is_nonprofit_or_h1b_cap_exempt, why_match. File pattern results/jobs_YYYYMMDD_HHMMSS.csv. Empty cells for None. Booleans rendered True/False/blank.

10. Preferences seed — job_requirements.md

Ship the exact same template currently in the repo (Job Titles, Location, Work Mode, Salary, Company Type, Must-Have, Nice-to-Have, Exclude) so the JS markdown parser keeps working unchanged.



11. Frontend — pixel-equivalent rebuild

The UI is what makes the app feel friendly; reproduce exactly:

11a. Color theme & typography (CSS variables in :root)





--bg: #faf7f2 (warm paper)



--surface: #ffffff



--ink: #2b2b2b / --ink-soft: #5b5b5b / --muted: #8a8a8a



--line: #ece6dc



--accent: #7ba890 (sage), --accent-deep: #5e8a73, --accent-glow: rgba(123,168,144,0.22)



Badge palette: --blush: #eef4f0, --petal: #9bc4a8, --lavender: #c8dbe7, --peach: #f0ebe3, --cream: #f4d9a3



--shadow: 0 4px 20px rgba(60,50,35,0.06)



Radii: --radius: 14px, --radius-sm: 10px, --radius-pill: 999px



Font: Google Fonts Nunito weights 400/600/700/800, fallback system-ui, -apple-system, 'Segoe UI', sans-serif. Body weight 500, line-height 1.5.

11b. Layout (index.html)





Topbar (.topbar, white surface, bottom border --line):





Brand: a 14px gradient circle (--accent → --accent-deep with --accent-glow ring), <h1>Job Seeker</h1> (1.45rem, weight 800), tagline "A friendly little agent that goes hunting for jobs that fit you."



Toolbar buttons (right-aligned, wrap on narrow screens): Find me jobs (primary, gradient sage), Job Requirements (secondary outline), Reload preferences (ghost), Download CSV (ghost, hidden until first run), History (ghost, hidden until at least one CSV exists).



Main container (max 1080px, padding 28×32):





#status-bar — single-line summary after a search (jobs found, elapsed, model code, saved-to path). Hidden initially.



#loading — three pulsing sage dots + "Searching the web for jobs that fit you… this can take a minute." Hidden when not searching.



#empty — friendly fallback when 0 results.



#controls — filter chips row (All, Remote, Hybrid, Non-profit / H1B-exempt, Has salary) plus Sort <select> (Best match, Newest first, Salary: high → low). Active chip uses gradient sage background, white text.



#results — vertical grid of cards.



Card (.card, white surface, soft shadow, hover lift 1px):





Head: title (1.1rem, weight 800) + company (--ink-soft, weight 600), with Posted ... timestamp top-right.



Badges row: location (lavender), work-mode (sage tint), salary (cream), Non-profit/H1B-exempt (gradient sage, white). Conditional rendering — only show badges with data.



why paragraph (--ink-soft, 0.95rem).



Actions: Open posting (secondary, target=_blank rel=noopener), Copy link (ghost, copies to clipboard, shows toast "Link copied").



Preferences modal (#modal-prefs, 720px max, scrollable body):





Backdrop: rgba(45,42,38,0.42) + 2px backdrop-blur.



One labeled <textarea> per section: Intro, Job titles, Location, Work mode, Salary, Company type, Must-have, Nice-to-have, Exclude, plus a hidden Additional sections box that appears only when extra Markdown exists outside the known headings.



Footer meta: "X lines in file · Y chars · unsaved changes".



Footer buttons: Cancel (ghost), Save (secondary), Save & Search (primary).



Cancel guard: if dirty, confirm("Discard unsaved changes?").



Keyboard: Esc cancels, Ctrl/Cmd+S saves.



History modal (#modal-history, 560px max): list of past CSV runs with filename, ISO timestamp, row count, KB size, and a Download button per row.



Toast (#toast, fixed bottom-center, gradient sage pill, fade in/out 200ms).



Footer (centered, white surface, top border): Model: <code>{{model}}</code> · Preferences: <code>{{preferences_path}}</code>.



Responsive: at max-width: 640px, topbar/container padding shrinks and toolbar buttons fill width (flex: 1).

11c. Frontend behavior (app/static/app.js)

Single IIFE, no framework. Reproduce verbatim:





Markdown ↔ form parser: splits on ## Heading, maps headings (Job Titles → job_titles, Must-Have → must_have, Nice-to-Have → nice_to_have, etc.). Unknown headings collected into the "Additional sections" textarea so nothing is lost on round-trip.



parseSalaryNumber() understands $80k, $80,000-$95,000, etc. (returns max value found).



parseDate() understands ISO dates and relative phrases like 3 days ago, 2 weeks ago.



Filter chips and sort dropdown re-render the cards client-side without re-querying the agent.



Find me jobs POSTs /api/search, shows the loading dots, hydrates #status-bar with "N jobs found in Xs using <model> · Saved to results/jobs_…csv".



Download CSV becomes visible after the first successful run; History becomes visible once /api/results returns a non-empty list.

11d. Favicon

Inline SVG of a small sage circle on transparent background — pick something simple (a magnifying glass over the brand-dot gradient). 32×32 viewbox.



12. Launchers





run_server.py: imports uvicorn, asks the OS for a free port via a temporary socket.bind(("127.0.0.1", 0)), prints http://127.0.0.1:<port>, runs uvicorn.run("app.main:app", host="127.0.0.1", port=port). Avoids Windows WinError 10013.



run.bat: changes to script dir, prefers .venv\Scripts\python.exe if present else python, runs python run_server.py.



run.command: same idea for macOS, prefers .venv/bin/python3. README notes chmod +x run.command first-time.



13. Tests (tests/)





test_config.py — verifies env defaults and that MAX_SEARCH_CALLS, MAX_OUTPUT_TOKENS, WHY_MATCH_MAX_CHARS honor env overrides.



test_requirements_loader.py — round-trip read/write + read_for_agent() strips blockquote intro and empty-value bullets.



test_csv_writer.py — column order, blanks for None, booleans as text.



test_agent.py — patch OpenAI.chat.completions.create with a fake that issues one tool call, then a final JSON message. Patch tavily_search. Assert: tool-loop terminates, final JSON parsed, MAX_SEARCH_CALLS enforced (a third tool call would cause an immediate JSON-format-only re-prompt), max_tokens and response_format arrive on the final call.



test_main.py — FastAPI TestClient: GET /, preferences round-trip, /api/search (with agent monkey-patched), CSV download path-traversal rejected.

CI: .github/workflows/tests.yml runs pip install -r requirements.txt && pytest -q on Ubuntu Python 3.11.



14. README highlights

Mirror the existing README's structure but swap the "OpenAI key" section for:





Get a free NVIDIA NIM key at build.nvidia.com → click any model → "Get API Key".



Get a free Tavily key at tavily.com (1000 searches/month).



Copy .env.example to .env, paste both keys.



Same Setup / Run / Using-the-app / CSV-output sections as today.



Add a Cost & limits subsection: "Both backends are free at the volumes this app uses. NIM has per-minute rate limits on the free tier; Tavily caps at ~1000 searches/month, so each app run uses up to 2 of those (≈500 runs/month)."



15. Build order (suggested for the implementing agent)





Scaffold repo + requirements.txt + .env.example + .gitignore + README.md skeleton.



app/config.py, app/schemas.py, app/requirements_loader.py (with read_for_agent), app/csv_writer.py.



app/search_provider.py (Tavily) — verify with a manual smoke test.



app/agent.py — tool-loop + structured outputs. Smoke test against NIM with a tiny prefs file.



app/main.py — FastAPI routes.



Frontend: index.html, styles.css, app.js, favicon.svg (port verbatim from existing repo's behavior; only swap the displayed model name).



run_server.py, run.bat, run.command.



Seed job_requirements.md.



Tests + GitHub Actions.



Manual end-to-end: edit prefs in modal → Save & Search → cards render → CSV downloads → History lists the run.