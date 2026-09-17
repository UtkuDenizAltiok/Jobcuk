#!/bin/bash
# For the owner: double-click to save a full backup copy of Jobcu's code,
# including its complete dated history, in Documents > Jobcu Backups.
# (Backs up code only. Nobody's personal data is ever in the code folder.)

cd "$(dirname "$0")/.." || exit 1
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"

backup_dir="${JOBCU_BACKUP_DIR:-$HOME/Documents/Jobcu Backups}"
stamp="$(date +%Y-%m-%d_%H%M)"
history_file="$backup_dir/Jobcu history $stamp.bundle"
files_zip="$backup_dir/Jobcu files $stamp.zip"

finish() {
  if [ -z "$JOBCU_BACKUP_DIR" ]; then
    echo
    read -r -p "Press Return to close this window. " _
  fi
  exit "$1"
}

mkdir -p "$backup_dir" || finish 1

echo "Getting the latest version from GitHub..."
if git fetch --quiet origin 2>/dev/null; then
  echo "  Done."
else
  echo "  Couldn't reach GitHub, so this backup uses the copy on this Mac."
fi

echo "Saving the complete history..."
if ! git bundle create "$history_file" --all >/dev/null 2>&1 \
  || ! git bundle verify "$history_file" >/dev/null 2>&1; then
  echo "  Something went wrong. No backup was made. Please tell Claude."
  finish 1
fi

echo "Saving the current files..."
if ! git archive --format=zip -o "$files_zip" HEAD; then
  echo "  Something went wrong. Please tell Claude."
  finish 1
fi

echo
echo "Backup finished. Two files were saved in: $backup_dir"
echo "  - Jobcu history $stamp.bundle  (the full project with every dated change)"
echo "  - Jobcu files $stamp.zip       (the current files, readable on any computer)"
echo
echo "Tip: also copy them to a USB drive or cloud storage, in case this Mac is lost."

if [ -z "$JOBCU_BACKUP_DIR" ]; then
  open "$backup_dir"
fi
finish 0
