# Instructions for AI coding assistants

This file is for **any AI coding tool** working on Jobcu: Claude Code, Codex, Cursor, GitHub
Copilot, Gemini CLI, Windsurf, Aider, Junie and others. Most read it automatically.
People should start with [CONTRIBUTING.md](CONTRIBUTING.md).

## What Jobcu is

Jobcu is a private job search app for the EU, the UK, Switzerland, Norway and Iceland. It runs
on the user's own Mac or Windows computer and is used through a browser. The user gives it a CV,
a cover letter and a free-text description of where they want to work. On **Search**, it collects
fresh job ads from as many sources as possible, removes duplicates, applies the location criteria,
scores each job against the user's profile with an AI model the user chose, and shows a ranked
list with short reasons.

## Read these first

1. [docs/HANDOVER.md](docs/HANDOVER.md): the original concept and **source of truth**. Never edit
   it. Record changes to the plan in `docs/DECISIONS.md` instead.
2. [docs/PROGRESS.md](docs/PROGRESS.md): which phase the project is in and what comes next.
3. [docs/DECISIONS.md](docs/DECISIONS.md): every decision so far, with dates and reasons.

## Who you are working with

The owner (Utku) and his invited friends. **Assume they have no programming experience**, unless
they say otherwise.

- Explain what you do and why in plain words. Explain any technical term the first time.
- For anything they must do themselves, give exact steps **one at a time** and confirm each one
  worked before the next. Remember that some use a Mac and some use Windows.
- Do the technical work yourself whenever you can.
- **Never ask anyone to paste an API key or password into the chat.** Keys are entered only in
  Jobcu's own settings screen. If a person allows it, an assistant running on their own computer
  may use the keys saved in Jobcu's data folder **through Jobcu's code** for real tests, without
  ever printing, logging or copying them. Use free usage only unless they agree to costs, and keep
  job-site requests modest (their keys have daily limits).
- Items marked **Decided** in HANDOVER.md belong to the owner. Changing one needs the owner's
  approval (for friends, that happens in the pull request). Also ask before adding any paid
  service or doing anything that affects someone's accounts or costs.

## Hard rules (never break these)

1. **No logins on job sites**, ever: no accounts, cookies or credentials. Never try to get past
   CAPTCHAs, logins or bot protection. If a site blocks Jobcu, back off and mark the source
   unavailable for that search.
2. **Device-local only:** no website, hosting, server, cloud storage, user accounts, analytics or
   telemetry. Jobcu connects only to job sources and to the AI provider the user chose.
3. **macOS and Windows are both fully supported.** Every feature, file path and launcher must work
   on both, and CI tests both.
4. **Stay neutral about AI providers.** Never recommend, prefer or default to one, in code, UI or
   docs. Never hard-code model names: users enter or pick them in settings.
5. **Never commit keys, CVs or personal data.** Tests use fake data only.
6. **The repository is private and its history is permanent:** never make it public, force-push,
   rewrite or squash shared history, or delete commits. Commit dates are the record of the
   owner's work.
7. English UI only. Supported countries only: EU countries, UK, Switzerland, Norway, Iceland.

## When goals conflict, decide in this order

1. Never break the hard rules.
2. Don't miss relevant fresh jobs. Coverage and freshness are Jobcu's main purpose.
3. Accurate filtering and scoring.
4. Simplicity for non-technical users.
5. Reasonable AI cost (the owner's budget is up to €30 a month), but never by lowering 2 or 3.
6. Speed matters least. A search may take minutes, but not hours.

## Project layout

```
Start Jobcu.command / .bat   double-click launchers (macOS / Windows)
src/jobcu/
  launcher.py                starts the local server and opens the browser
  app.py                     FastAPI app: screen, internal API, local-only safety checks
  paths.py                   the per-user data folder (never inside the code folder)
  keystore.py                API keys, saved in the data folder, readable only by the user
  settings.py                all other settings (settings.json in the data folder)
  settings_api.py            internal API behind the Settings screen
  documents.py               CV and cover letter: saving uploads and reading their text
  documents_api.py           internal API for documents and the profile preview
  profile.py                 the AI prompt that reads documents into a profile
  countries.py               supported countries and their job-ad languages
  location.py                understands "Where do you want to work?"
  keywords.py                the hidden multilingual search words
  search.py                  runs a search step by step in the background, with progress
  pipeline.py                collecting from sources, full ads, result cards
  dedupe.py                  duplicates, main link, "possible duplicate"
  filters.py                 the free rules filter (dates, types, remote, country, dismissed)
  relevance.py               the quick AI relevance check
  scoring.py                 the scoring rubric and prompt
  freshness.py               posting dates and "Posted within"
  jobstore.py                jobs remembered between searches, job states, saved results
  text.py                    job ad HTML to plain text
  jobposting.py              reads schema.org JobPosting data from job pages
  search_api.py              internal API for starting and following a search
  build.py                   code fingerprint, so a new Jobcu replaces an older running one
  db.py                      SQLite database with numbered migrations
  logs.py                    log file in the data folder, with keys hidden
  ai/                        the AI layer: client.py is the ONLY way to call an AI;
                             one adapter per provider; providers.py lists them
  sources/                   job sources: base.py (common interface), http.py (polite
                             requests), budget.py (free usage limits), one module per source
  web/                       the screen: plain HTML, CSS, JS (no build step)
tests/                       pytest; conftest.py gives every test a throwaway data folder
tools/check_no_secrets.py    safety check against keys and personal data (Git hook and CI)
.githooks/pre-commit         runs the safety check before every commit
.github/workflows/tests.yml  CI: safety check, then tests on macOS and Windows
docs/                        HANDOVER, DECISIONS, PROGRESS, guides/
```

## Commands

```bash
uv sync                                  # install everything (uv also installs Python 3.13)
git config core.hooksPath .githooks      # turn on the safety check (once per copy)
uv run pytest                            # run the tests
uv run ruff check .                      # check code style
uv run jobcu                             # start Jobcu
```

Environment variables: `JOBCU_DATA_DIR` uses another data folder, `JOBCU_NO_BROWSER=1` doesn't open
the browser, and `JOBCU_SELFTEST=1` starts Jobcu, checks that it answers, then stops.

## Conventions

- **Python 3.13 with uv.** Add dependencies with `uv add` (or `uv add --dev`) and commit `uv.lock`.
- **Style:** Ruff, line length 100. Comments explain *why*, in plain words.
- **Tests:** every change comes with tests, and they must pass on macOS and Windows. Use `pathlib`,
  never OS-specific path strings, and always pass `encoding="utf-8"` when reading or writing text.
- **Screen:** plain HTML/CSS/JS in `src/jobcu/web/`. No build tools, CDNs, web fonts or outside
  scripts. The Content-Security-Policy and a test enforce this.
- **Local server:** listens on 127.0.0.1 only. Requests that change data must send the header
  `X-Jobcu: 1` from Jobcu's own page. Other requests are refused.
- **User data** (documents, jobs, job states, settings, keys) lives only under `paths.data_dir()`.
- **Keys** go through `keystore.KeyStore`. Never log them, and show them only masked.
- **AI calls** (from Phase 1) all go through one provider layer, never directly to a provider SDK
  from elsewhere, so switching provider is only a settings change.
- **Job sources** (from Phase 1): one isolated adapter per source behind a common interface. A
  failing source must never break a search. Be polite: limit request rates, back off on errors
  and respect `Retry-After`.
- **Text users see:** friendly, plain English without jargon.

## Workflow

- Make small, focused commits with clear messages, and keep docs in step with the code.
- Record each decision in `docs/DECISIONS.md` (date, decision, one-line reason), and update
  `docs/PROGRESS.md` when something is finished.
- Before committing: `uv run ruff check .` and `uv run pytest`. The safety hook must be on.
- Friends work on a branch in their own copy and open a pull request. The owner approves merges.
