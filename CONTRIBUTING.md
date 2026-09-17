# Developer guide

Technical documentation for people and AI assistants working on Jobcu. Everyday users should read
the [README](README.md) instead.

Jobcu is **private** (invited people only) and **not open source**: by contributing, you agree that
your changes become part of Jobcu under its [LICENSE](LICENSE).

## Documents

| File | What it's for |
|---|---|
| [AGENTS.md](AGENTS.md) | Rules, conventions, project layout, lessons learned (read first; AI tools load it automatically) |
| [docs/PROGRESS.md](docs/PROGRESS.md) | **"Right now"**: current state and next tasks, plus the phase checklists |
| [docs/DECISIONS.md](docs/DECISIONS.md) | Every decision with date and reason (newer entries override older ones) |
| [docs/SOURCES.md](docs/SOURCES.md) | Verified facts, limits and quirks of each job source |
| [docs/HANDOVER.md](docs/HANDOVER.md) | Original concept and source of truth (never edited) |
| [docs/guides/](docs/guides/) | Everyday-user guides; keep them in step with the app |

## Stack

Python 3.13 managed by **uv**, **FastAPI** + Uvicorn on 127.0.0.1, **SQLite**, plain HTML/CSS/JS (no
build step, no external resources), official AI provider SDKs behind one layer (`src/jobcu/ai/`),
**httpx** for job sources, **pytest** + **Ruff**. CI (GitHub Actions) runs a secrets check and the
tests on macOS and Windows.

## Setup

Mac: `brew install git uv gh` · Windows: `winget install --id Git.Git -e`,
`winget install --id astral-sh.uv -e`, `winget install --id GitHub.cli -e`

```bash
gh auth login
gh repo fork UtkuDenizAltiok/jobcu --clone   # or clone directly if you have write access
cd jobcu
uv sync
git config core.hooksPath .githooks          # secrets check before every commit
uv run pytest && uv run ruff check .
uv run jobcu                                 # JOBCU_DATA_DIR=... for a separate data folder
```

## How a search works

`search.py` runs these steps in a background thread, with progress polled by the screen:

documents → profile (`profile.py`) → location plan (`location.py`) → search words (`keywords.py`)
→ sources in parallel (`pipeline.collect`, `sources/*`) → duplicates (`dedupe.py`) → rules filter
(`filters.py`) → quick relevance check (`relevance.py`) → full ads (`load_details`) → scoring
(`scoring.py`) → cards and job memory (`pipeline.build_card`, `jobstore.py`).

## Workflow

1. Read "Right now" in `docs/PROGRESS.md` and the relevant decisions.
2. Work on a branch; every change comes with tests (mock HTTP and AI; never contact real sites in
   tests).
3. `uv run ruff check . && uv run pytest` must pass. Never commit keys, CVs or personal data.
4. Record decisions in `docs/DECISIONS.md`, update "Right now", and update user guides if screens
   change.
5. Open a pull request (`gh pr create`). CI must pass on macOS and Windows; the owner approves merges.
   Never force-push or rewrite history.
