"""Where Jobcu keeps each person's data on their own computer.

The data folder is deliberately separate from the app's code folder, so
downloading a new version of Jobcu never touches it:

- macOS:   ~/Library/Application Support/Jobcu
- Windows: C:\\Users\\<name>\\AppData\\Local\\Jobcu

Setting the JOBCU_DATA_DIR environment variable uses another folder instead
(the tests use this so they never touch real data).
"""

import os
from pathlib import Path

from platformdirs import user_data_dir

APP_NAME = "Jobcu"
DATA_DIR_ENV = "JOBCU_DATA_DIR"

_README_TEXT = """\
This folder holds your personal Jobcu data: settings, API keys, saved and
dismissed jobs. It stays on this computer and is never uploaded anywhere.

- Updating Jobcu does not change this folder.
- Do not share this folder with anyone: it contains your API keys.
- Deleting this folder erases all your Jobcu data and settings.
"""


def data_dir() -> Path:
    """Return the data folder path (without creating it)."""
    override = os.environ.get(DATA_DIR_ENV)
    if override:
        return Path(override).expanduser().resolve()
    # roaming=False keeps the data on this computer on Windows (AppData\\Local).
    return Path(user_data_dir(APP_NAME, appauthor=False, roaming=False))


def ensure_data_dir() -> Path:
    """Create the data folder if needed and return its path."""
    folder = data_dir()
    folder.mkdir(parents=True, exist_ok=True)
    if os.name == "posix":
        folder.chmod(0o700)  # only this user account can open it
    readme = folder / "README.txt"
    if not readme.exists():
        readme.write_text(_README_TEXT, encoding="utf-8")
    return folder


def code_dir() -> Path:
    """Return the folder that holds Jobcu's own code."""
    return Path(__file__).resolve().parent
