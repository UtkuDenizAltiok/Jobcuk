"""A fingerprint of Jobcu's code, so a newer copy can recognise an older one still running."""

import hashlib
from functools import cache
from pathlib import Path

_PACKAGE = Path(__file__).resolve().parent


@cache
def build_id() -> str:
    digest = hashlib.sha256()
    for path in sorted(_PACKAGE.rglob("*")):
        if path.is_file() and path.suffix in {".py", ".html", ".css", ".js", ".svg", ".json"}:
            digest.update(path.relative_to(_PACKAGE).as_posix().encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()[:16]
