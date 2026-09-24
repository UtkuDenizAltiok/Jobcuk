"""Jobcu's settings: everything the user chooses except API keys (see keystore.py).

Saved as settings.json in the data folder. A damaged file is set aside and
defaults are used, so Jobcu always starts.
"""

import json
import os
import tempfile
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, ValidationError, model_validator

from jobcu.paths import ensure_data_dir

SETTINGS_FILENAME = "settings.json"

ProviderId = Literal["anthropic", "gemini", "openai", "openai_compatible"]
Effort = Literal["minimal", "low", "medium", "high"]


class AISettings(BaseModel):
    provider: ProviderId | None = None
    model: str = ""
    # Optional second model for the few reasoning-heavy steps (reading the CV and
    # cover letter, understanding the location text). Empty means "use `model`".
    reasoning_model: str = ""
    # Only for "Other (OpenAI-compatible)" providers.
    base_url: str = ""
    # Reasoning effort per kind of step: medium everywhere, the owner's choice (2026-09-24).
    # `scoring_effort` is for the many small steps (quick check, scoring), `reasoning_effort` for
    # reading documents and places and for web look-ups. Models that don't support a setting
    # simply ignore it (see ai/client.py).
    scoring_effort: Effort | None = "medium"
    reasoning_effort: Effort | None = "medium"


class LimitSettings(BaseModel):
    # When a cap is reached, Jobcu asks before continuing. It never skips silently.
    scoring_cap: int = Field(default=200, ge=1)
    # Web look-ups in one search, for the conditions someone wrote about places.
    # Understanding the location takes about 10; finding where the best jobs are uses the rest.
    web_search_cap: int = Field(default=50, ge=0)
    # Optional monthly limits. AI work stops when one is reached.
    monthly_token_limit: int | None = Field(default=None, ge=1)
    monthly_cost_limit: float | None = Field(default=None, gt=0)
    # Google Maps, with the person's own key: kept below Google's free monthly allowance of
    # 10,000 route-matrix elements (checked 2026-09-21).
    maps_monthly_routes: int = Field(default=9000, ge=0)


class ModelPrice(BaseModel):
    """What a model costs, entered by the user, so Jobcu can estimate money spent."""

    provider: ProviderId
    model: str
    input_per_million: float = Field(ge=0)
    output_per_million: float = Field(ge=0)
    currency: str = "USD"


JobType = Literal[
    "full_time_permanent",
    "fixed_term",
    "part_time",
    "internship_or_working_student",
    "freelance_or_contract",
]
JOB_TYPES: tuple[str, ...] = JobType.__args__  # type: ignore[attr-defined]


class SearchForm(BaseModel):
    """What the user filled in on the search screen, kept for their next visit."""

    location_text: str = Field(default="", max_length=2000)
    # What the documents don't say, such as citizenship or a newer language level (profile.py).
    about_you: str = Field(default="", max_length=500)
    posted_within_hours: Literal[6, 24, 72, 168] = 24
    job_types: list[JobType] = list(JOB_TYPES)
    exclude_remote: bool = False


# Settings files from before version 2 hold "low" for scoring, the old default nobody could change
# on screen; the owner then chose medium everywhere (DECISIONS.md, 2026-09-24).
SETTINGS_VERSION = 2


class Settings(BaseModel):
    version: int = SETTINGS_VERSION
    ai: AISettings = AISettings()
    search_form: SearchForm = SearchForm()
    limits: LimitSettings = LimitSettings()
    prices: list[ModelPrice] = []
    use_web_search: bool = True
    # Sources are all on unless switched off here.
    sources_disabled: list[str] = []

    @model_validator(mode="before")
    @classmethod
    def _upgrade(cls, data):
        if isinstance(data, dict) and data.get("version", 1) < SETTINGS_VERSION:
            ai = data.get("ai")
            if isinstance(ai, dict) and ai.get("scoring_effort") == "low":
                data = {**data, "ai": {**ai, "scoring_effort": "medium"}}
            data = {**data, "version": SETTINGS_VERSION}
        return data


def settings_path(folder: Path | None = None) -> Path:
    return (folder if folder is not None else ensure_data_dir()) / SETTINGS_FILENAME


def load_settings(folder: Path | None = None) -> Settings:
    path = settings_path(folder)
    try:
        return Settings.model_validate_json(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return Settings()
    except (OSError, ValueError, ValidationError):
        os.replace(path, path.with_name(SETTINGS_FILENAME + ".damaged"))
        return Settings()


def save_settings(settings: Settings, folder: Path | None = None) -> None:
    path = settings_path(folder)
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=".settings-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as tmp:
            json.dump(settings.model_dump(mode="json"), tmp, indent=2)
        os.replace(tmp_name, path)
    except BaseException:
        Path(tmp_name).unlink(missing_ok=True)
        raise
