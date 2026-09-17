# Helping build Jobcu

Thanks for helping! Jobcu is a **private** project. Only people the owner has invited can see it.
You don't need to be a programmer: most changes can be made together with an AI coding assistant.

## The short version

1. Read the [README](README.md) to see what Jobcu does, and [docs/PROGRESS.md](docs/PROGRESS.md)
   to see what's being worked on.
2. Set up your computer once (below).
3. Make your change in **your own copy** of the project, then send it to the owner as a
   **pull request** (a proposed change the owner can review and accept).

## Ground rules

- **Never add real personal data** to the project: no API keys, passwords, CVs, cover letters,
  or saved Jobcu data. An automatic check blocks most of these, but please take care.
- **Keep Jobcu private.** Don't share its code or documents outside the invited group.
- **Keep the history.** Never force-push or delete commits. The history is the record of how
  Jobcu was made.
- **Big changes to the plan** (anything marked *Decided* in [docs/HANDOVER.md](docs/HANDOVER.md))
  need the owner's approval.
- **Stay neutral about AI providers.** Jobcu never recommends one.
- Everything must work on **both Mac and Windows**.

The full rules are in [AGENTS.md](AGENTS.md), written for AI assistants but readable by anyone.

## Using an AI coding assistant

Most AI coding tools automatically read [AGENTS.md](AGENTS.md), which explains the project, the
rules and the commands. This includes Claude Code, Codex, Cursor, GitHub Copilot, Gemini CLI,
Windsurf, Junie and Aider. The project already includes the small settings files that Gemini CLI
and Aider need. You can simply tell your assistant: *"Read AGENTS.md, then help me with …"*.

**Never paste API keys or passwords into an AI chat.**

## Setting up your computer (once)

A **terminal** is a window where you type commands. Paste each line below, then press
Return (Mac) or Enter (Windows). Your AI assistant can also do this for you.

### Mac

Open **Terminal** (press Command + Space, type `Terminal`, press Return).

1. If you don't have Homebrew (a free tool installer), install it by following the instructions
   on [brew.sh](https://brew.sh).
2. Install Git, uv and the GitHub tool:
   ```bash
   brew install git uv gh
   ```

### Windows

Open **PowerShell** (press the Windows key, type `PowerShell`, press Enter).

1. Install Git, uv and the GitHub tool:
   ```powershell
   winget install --id Git.Git -e
   winget install --id astral-sh.uv -e
   winget install --id GitHub.cli -e
   ```
2. Close PowerShell and open it again, so it finds the new tools.

### Both: get your own copy of Jobcu

```bash
gh auth login
gh repo fork UtkuDenizAltiok/jobcu --clone
cd jobcu
uv sync
git config core.hooksPath .githooks
uv run pytest
```

What these do, line by line:

- `gh auth login` connects your terminal to your GitHub account. Choose the options the screen
  offers and let it open your browser.
- `gh repo fork … --clone` makes your own private copy of Jobcu on GitHub (a "fork") and
  downloads it to your computer.
- `cd jobcu` moves into the downloaded folder.
- `uv sync` installs Python and everything Jobcu needs. This takes a minute the first time.
- `git config core.hooksPath .githooks` turns on the safety check that stops keys and personal
  data from being committed.
- `uv run pytest` runs the automatic tests. They should all pass.

## Running Jobcu from your copy

Double-click **Start Jobcu.command** (Mac) or **Start Jobcu.bat** (Windows), or run `uv run jobcu`.
Your Jobcu data is stored outside the project folder, so it's never part of the code.

## Making and sending a change

1. Start a new branch, a separate line of work, with a short name for your change:
   ```bash
   git checkout -b short-name-for-your-change
   ```
2. Make the change, with or without your AI assistant.
3. Check it:
   ```bash
   uv run ruff check .
   uv run pytest
   ```
4. Save and upload it:
   ```bash
   git add -A
   git commit -m "Describe the change in one sentence"
   git push -u origin short-name-for-your-change
   ```
5. Send it to the owner:
   ```bash
   gh pr create
   ```
   Explain what you changed and why. GitHub automatically runs the tests on Mac and Windows.
   The owner reviews the change and accepts it, or asks for changes.

Also add a short entry to [docs/DECISIONS.md](docs/DECISIONS.md) for any decision your change
makes, and update [docs/PROGRESS.md](docs/PROGRESS.md) if you finished something on the list.

## Reporting a problem or suggesting an idea

Open the **Issues** tab on the project's GitHub page and click **New issue**. Simple forms help you
describe the problem or idea in plain words. Never include keys or personal documents.

## Rights

Jobcu isn't open source. By contributing, you agree that your changes become part of Jobcu and are
covered by its [LICENSE](LICENSE).
