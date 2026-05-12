# Job Seeker v2

A small FastAPI web app that finds U.S. job postings from your Markdown preferences using **Google Gemini** (chat + tools + structured JSON) and **Tavily** for live web search.

## Compared to [job-seeker](https://github.com/danishb7/job-seeker)

This repository mirrors the **same idea and UX** as [danishb7/job-seeker](https://github.com/danishb7/job-seeker): one `job_requirements.md` file, **Find me jobs**, CSV history, filters, and the preferences modal. The difference is the backend:

- **LLM**: **Google Gemini** via [Google AI Studio](https://aistudio.google.com/apikey), which provides a **free API key tier within usage quotas** (see [Gemini pricing](https://ai.google.dev/pricing)) instead of the original OpenAI-based stack.
- **Web search**: **Tavily** (optional free tier ~1000 searches/month) instead of the built-in provider web search tool.
- **Token-focused behavior**: capped web searches per run (`MAX_SEARCH_CALLS`), structured JSON for the final job list (schema enforced, not long prose), concise system instructions, **full preferences read verbatim from Markdown** (including location and search domains in the file—not duplicated in `.env`), and Tavily queries trimmed to the API **400-character** limit so requests do not fail.

If you want the original OpenAI-oriented implementation, use the [job-seeker](https://github.com/danishb7/job-seeker) repo.

---

- One editable file ([`job_requirements.md`](job_requirements.md)) drives every search.
- Click **Find me jobs** to run the agent across the domains you list under `## Search domains`.
- Every run is auto-saved as a CSV in `results/`.

## Setup

1. Create a virtual environment:
   ```bash
   python -m venv .venv
   ```
   Activate it:
   - Windows PowerShell: `.\.venv\Scripts\Activate.ps1`
   - macOS/Linux: `source .venv/bin/activate`
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Get API keys:
   - **Gemini**: create a key in [Google AI Studio](https://aistudio.google.com/apikey) (Google account).
   - **Tavily**: sign up at [tavily.com](https://tavily.com).
4. Copy `.env.example` to `.env` and set `GEMINI_API_KEY`, `TAVILY_API_KEY`, and optionally `GEMINI_MODEL` (default is `gemini-2.5-flash` in [`app/config.py`](app/config.py)).
5. Edit [`job_requirements.md`](job_requirements.md) (or use **Job requirements** in the app). Put **location**, **visa rules**, and **which sites to search** in that file—especially the `## Search domains` section, which limits Tavily to the hostnames you list.
6. Run the app:
   - Windows (double-click): `run.bat`
   - macOS (double-click after first `chmod +x run.command`): `run.command`
   - Terminal: `python run_server.py`

## Using the app

- **Find me jobs** runs a search and renders cards.
- **Job requirements** opens the structured editor for `job_requirements.md` (intro quote, sections, and optional extra headings).
- **Reload preferences** re-reads `job_requirements.md` from disk.
- **Download CSV** appears after first successful run.
- **History** appears once at least one CSV exists.

## CSV output

Each run writes `results/jobs_YYYYMMDD_HHMMSS.csv` with columns:

- `title`
- `company`
- `type`
- `location`
- `salary`
- `posting_date`
- `link`
- `source`
- `is_nonprofit_or_h1b_cap_exempt`
- `why_match`

## Cost and limits

- **Tavily**: free tier is on the order of ~1000 searches per month; this app uses at most **2** Tavily calls per run (`MAX_SEARCH_CALLS`), so budget roughly **~500 runs/month** on a 1000/month quota.
- **Gemini**: Google AI Studio offers **free usage within quotas**; limits and eligible models change over time. See [Gemini pricing and rate limits](https://ai.google.dev/pricing). The app retries once on transient API errors.

## Tests

```bash
pytest -q
```

CI runs the same on push/PR via [`.github/workflows/tests.yml`](.github/workflows/tests.yml).
