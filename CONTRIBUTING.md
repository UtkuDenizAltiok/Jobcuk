# Contributing to Jobcu

Jobcu is **private** (invited people only) and **not open source**: by contributing, you agree that
your changes become part of Jobcu under its [LICENSE](LICENSE). Everyday users need only the
[README](README.md).

Everything about how Jobcu is built and worked on is in **[AGENTS.md](AGENTS.md)**, the one
rulebook for people and AI assistants alike. This page only gets you started.

## Set up

Mac: `brew install git uv gh` · Windows: `winget install --id Git.Git -e`,
`winget install --id astral-sh.uv -e`, `winget install --id GitHub.cli -e`

```bash
gh auth login
gh repo fork UtkuDenizAltiok/jobcu --clone   # or clone directly if you have write access
cd jobcu
uv sync
git config core.hooksPath .githooks          # safety check before every commit
uv run pytest && uv run ruff check .
uv run jobcu
```

## Working with an AI assistant

Any capable AI coding assistant works: Claude Code, Codex, Gemini CLI, Cursor, GitHub Copilot,
Aider, or a chat assistant such as ChatGPT, Gemini, Grok or Kimi. Open the project folder in your
assistant and paste these prompts as they are.

**At the start of every session:**

```text
You are joining Jobcu, a private job search app. First read AGENTS.md in full and follow it: it
is the project's rulebook. Then do what its section "Starting, or resuming after any
interruption" says: read "Right now" in docs/PROGRESS.md and check the repository's real state.
Tell me in plain words where the project stands, anything unfinished or needing a check, what is
waiting on me, and what you propose to do next. Wait for my go-ahead before large changes. If you
can't open files yourself, ask me to paste AGENTS.md and docs/PROGRESS.md.
```

**Before you stop, or when the conversation is getting full:**

```text
Wrap up for a fresh session: follow the section "Ending a session" in AGENTS.md. Stop at a safe
point, make sure everything important from this session is recorded in the repository (not only
in this chat), check the tests, commit and push. Then tell me in a few lines what was done, what
comes next, what is waiting on me, and whether it's safe to start a new session.
```

## Changes

Work on a branch, keep every change tested (`uv run ruff check . && uv run pytest`), and open a
pull request (`gh pr create`). GitHub runs the tests on macOS and Windows; the owner approves
merges. Never force-push or rewrite history.
