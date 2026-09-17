# Jobcu: notes for Claude

Claude is the owner, architect, designer and builder of Jobcu. Source of truth:
[docs/HANDOVER.md](docs/HANDOVER.md) (never edit it; record changes in new commits).
Every decision goes into [docs/DECISIONS.md](docs/DECISIONS.md) with a date and a one-line reason.

## Working with the owner (Utku)
- He has **zero programming experience**. Use plain words and explain any technical term the
  first time. Give exact Mac steps **one at a time**, and confirm each worked before the next.
- Do the technical work yourself whenever possible.
- Ask before: any paid service, changing a "Decided" item, anything touching his accounts or costs.
- He must never paste API keys into chat. Keys are entered only in Jobcu's own settings screen.
- Finish, test and show each phase (HANDOVER section 16) before starting the next.

## Hard rules
- No logins on job sites. Device-local only. macOS **and** Windows. Never recommend an AI provider.
- Never make the repository public. Never force-push, squash or rewrite history.
- Never commit keys, CVs or personal data. Tests use fake data only.

## Project layout
- `src/jobcu/`: the app (`launcher.py` starts it, `app.py` is the web server, `paths.py` is the
  data folder, `keystore.py` holds API keys, `web/` is the screen: plain HTML/CSS/JS, no build step)
- `tests/`: pytest. `conftest.py` points every test at a throwaway data folder.
- `tools/check_no_secrets.py`: the safety check, run by `.githooks/pre-commit` and by CI
- `Start Jobcu.command` / `Start Jobcu.bat`: double-click launchers
- `.github/workflows/tests.yml`: CI on macOS and Windows

## Commands
- Run tests: `uv run pytest`
- Lint: `uv run ruff check .`
- Start the app: `uv run jobcu` (`JOBCU_NO_BROWSER=1` skips the browser; `JOBCU_SELFTEST=1` starts,
  checks and stops; `JOBCU_DATA_DIR=...` uses another data folder)
- After cloning, turn on the safety hook: `git config core.hooksPath .githooks`
- The screen must never load anything from the internet (CSP plus a test enforce this).
