"""Jobcu's log file, for troubleshooting: logs/jobcu.log in the data folder.

The log never contains CV or cover letter text, prompts, or keys. As a safety net,
anything that looks like a key is hidden before it is written.
"""

import logging
import re
from logging.handlers import RotatingFileHandler

from jobcu.paths import ensure_data_dir

_KEY_LIKE = re.compile(
    r"\b(?:sk-[A-Za-z0-9_-]{12,}|AIza[0-9A-Za-z_-]{20,}|gh[pousr]_[A-Za-z0-9]{20,}"
    r"|[A-Za-z0-9_-]{32,})\b"
)


class RedactKeys(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        record.msg = _KEY_LIKE.sub("[hidden]", message)
        record.args = None
        return True


def setup_logging() -> None:
    folder = ensure_data_dir() / "logs"
    folder.mkdir(exist_ok=True)
    handler = RotatingFileHandler(
        folder / "jobcu.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8"
    )
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    handler.addFilter(RedactKeys())
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(handler)
    # The HTTP libraries log every request address at INFO level; keep only problems.
    for noisy in ("httpx", "httpx2", "httpcore", "google_genai", "openai", "anthropic"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
