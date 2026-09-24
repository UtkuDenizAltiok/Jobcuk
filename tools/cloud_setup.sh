#!/bin/bash
# Prepares a Claude Code cloud session (claude.ai/code, AGENTS.md "Working in a cloud session"):
# the project's packages and Python 3.13 through uv, and the safety check before every commit.
# Local sessions skip it: people set up once (CONTRIBUTING.md). It never stops a session from
# starting, and it says what failed so the session can fix it.

if [ "$CLAUDE_CODE_REMOTE" != "true" ]; then
  exit 0
fi
cd "${CLAUDE_PROJECT_DIR:-.}" || exit 0

git config core.hooksPath .githooks
if uv sync --quiet; then
  echo "Jobcu cloud setup: packages ready."
else
  echo "Jobcu cloud setup: 'uv sync' failed. Run it again before testing; if Python 3.13 can't"
  echo "be downloaded, the environment's network access may not be set to Full."
fi
exit 0
