#!/bin/bash
# Double-click this file to start Jobcu on a Mac.
# Keep the window that opens while you use Jobcu. Close it to stop Jobcu.

cd "$(dirname "$0")" || exit 1
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"

finish() {
  # Keep the window open so the message can be read.
  if [ "$JOBCU_SELFTEST" != "1" ]; then
    echo
    read -r -p "Press Return to close this window. " _
  fi
  exit "$1"
}

has_uv() {
  [ "$JOBCU_TEST_PRETEND_NO_UV" != "1" ] && command -v uv >/dev/null 2>&1
}

if ! has_uv; then
  echo "Jobcu needs a free helper program called \"uv\" to run. It downloads Python and the"
  echo "other parts Jobcu needs. This happens only once and takes a few minutes."
  echo
  if [ "$JOBCU_SELFTEST" != "1" ]; then
    read -r -p "Press Return to install it now, or close this window to cancel. " _
  fi
  if [ "$JOBCU_TEST_SKIP_INSTALL" = "1" ]; then
    echo "(Test: installation skipped.)"
  else
    # The official installer from uv's makers (astral.sh). It installs into ~/.local/bin and
    # doesn't change anything else on the Mac.
    curl -LsSf https://astral.sh/uv/install.sh | env UV_NO_MODIFY_PATH=1 sh
  fi
  export PATH="$HOME/.local/bin:$PATH"
  if [ "$JOBCU_TEST_SKIP_INSTALL" != "1" ] && ! command -v uv >/dev/null 2>&1; then
    echo
    echo "The helper couldn't be installed. Please check your internet connection and try again."
    echo "More help: docs/guides/troubleshooting.md in the Jobcu folder."
    finish 1
  fi
  if [ "$JOBCU_TEST_SKIP_INSTALL" = "1" ]; then
    finish 0
  fi
fi

# A copy made with git (the owner's, developers') first updates itself from GitHub, so it runs
# the newest version: only when nothing is changed here and it's on main, never asking for a
# password. If the update fails, the version already here starts. Copies from a ZIP skip this.
update_from_github() {
  [ "$JOBCU_SELFTEST" = "1" ] && return
  { [ -d .git ] && command -v git >/dev/null 2>&1; } || return
  [ -z "$(git status --porcelain --untracked-files=no 2>/dev/null)" ] || return
  [ "$(git rev-parse --abbrev-ref HEAD 2>/dev/null)" = "main" ] || return
  echo "Checking for a newer Jobcu..."
  GIT_TERMINAL_PROMPT=0 git pull --ff-only --quiet 2>/dev/null ||
    echo "Jobcu couldn't be updated right now, so it starts the version you have."
}
update_from_github

echo "Preparing Jobcu. The first start can take a few minutes..."
uv run --frozen --no-dev --quiet jobcu
status=$?
if [ "$status" -ne 0 ]; then
  echo
  echo "Jobcu stopped because of a problem. See the messages above."
  echo "More help: docs/guides/troubleshooting.md in the Jobcu folder."
  finish "$status"
fi
