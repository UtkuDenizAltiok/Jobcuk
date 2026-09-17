"""API keys, stored only in the local data folder.

Keys live in `keys.json` inside the data folder (see paths.py), which only the
current user account can read. They are never written to the code folder,
never logged, and only ever sent to the service each key belongs to.
"""

import json
import os
import tempfile
from pathlib import Path

from jobcu.paths import ensure_data_dir

KEYS_FILENAME = "keys.json"


class KeyStoreError(Exception):
    """A plain-language problem with the saved keys."""


class KeyStore:
    def __init__(self, folder: Path | None = None) -> None:
        self._folder = folder

    @property
    def path(self) -> Path:
        folder = self._folder if self._folder is not None else ensure_data_dir()
        return folder / KEYS_FILENAME

    def get(self, name: str) -> str | None:
        return self._load().get(name)

    def has(self, name: str) -> bool:
        return bool(self.get(name))

    def names(self) -> list[str]:
        return sorted(self._load())

    def set(self, name: str, value: str) -> None:
        value = value.strip()
        if not value:
            raise KeyStoreError("The key is empty. Please paste the whole key.")
        try:
            keys = self._load()
        except KeyStoreError:
            self._set_aside_damaged_file()
            keys = {}
        keys[name] = value
        self._save(keys)

    def delete(self, name: str) -> None:
        keys = self._load()
        if keys.pop(name, None) is not None:
            self._save(keys)

    def _load(self) -> dict[str, str]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {}
        except (OSError, ValueError) as exc:
            raise KeyStoreError(
                "Jobcu couldn't read your saved API keys. "
                "Please enter them again in Settings."
            ) from exc
        if not isinstance(data, dict) or not all(
            isinstance(k, str) and isinstance(v, str) for k, v in data.items()
        ):
            raise KeyStoreError(
                "Jobcu couldn't read your saved API keys. "
                "Please enter them again in Settings."
            )
        return data

    def _save(self, keys: dict[str, str]) -> None:
        path = self.path
        # Write to a temporary file first, then swap it in, so a crash can
        # never leave a half-written keys file behind.
        fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=".keys-", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as tmp:
                json.dump(keys, tmp, indent=2, sort_keys=True)
            if os.name == "posix":
                os.chmod(tmp_name, 0o600)  # readable only by this user account
            os.replace(tmp_name, path)
        except BaseException:
            Path(tmp_name).unlink(missing_ok=True)
            raise

    def _set_aside_damaged_file(self) -> None:
        path = self.path
        if path.exists():
            os.replace(path, path.with_name(KEYS_FILENAME + ".damaged"))


def mask(value: str) -> str:
    """Show only the end of a key, e.g. '••••3f9a', so it can be recognised safely."""
    value = value.strip()
    if len(value) <= 8:
        return "••••"
    return "••••" + value[-4:]
