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

if ! command -v uv >/dev/null 2>&1; then
  echo "Jobcu can't start yet: a free helper tool called uv is missing."
  echo "Please follow the installation guide in Jobcu's docs folder."
  finish 1
fi

echo "Preparing Jobcu. The first start can take a minute..."
uv run --frozen --no-dev --quiet jobcu
status=$?
if [ "$status" -ne 0 ]; then
  echo
  echo "Jobcu stopped because of a problem. See the messages above."
  finish "$status"
fi
