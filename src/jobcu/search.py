"""Runs a search in the background and reports its progress (HANDOVER sections 3 and 9).

A search is a list of steps. Each step updates what the screen shows, so the user
can see what Jobcu is doing. Only one search runs at a time. Every search starts
fresh from the current CV, cover letter and location text.
"""

import json
import logging
import threading
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Literal

from jobcu import db, documents
from jobcu.ai.base import AIError
from jobcu.ai.client import AIClient
from jobcu.ai.usage import UsageLog
from jobcu.countries import COUNTRIES, LANGUAGE_NAMES, languages_for
from jobcu.documents import DocumentError
from jobcu.keystore import KeyStore
from jobcu.keywords import generate_search_words
from jobcu.location import interpret_location
from jobcu.profile import read_profile
from jobcu.settings import SearchForm, load_settings

log = logging.getLogger(__name__)

StepStatus = Literal["waiting", "running", "done", "failed", "skipped"]
RunStatus = Literal["running", "finished", "failed", "stopped"]

STEPS: list[tuple[str, str]] = [
    ("documents", "Reading your CV and cover letter"),
    ("profile", "Understanding your profile"),
    ("location", "Understanding where you want to work"),
    ("search_words", "Preparing search words"),
    ("sources", "Searching job sources"),
]


@dataclass
class Step:
    id: str
    label: str
    status: StepStatus = "waiting"
    detail: str = ""


@dataclass
class SearchRun:
    id: int
    form: SearchForm
    started_at: str
    status: RunStatus = "running"
    steps: list[Step] = field(default_factory=lambda: [Step(i, label) for i, label in STEPS])
    notes: list[str] = field(default_factory=list)
    error: str | None = None
    result: dict = field(default_factory=dict)
    stop_requested: bool = False
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def step(self, step_id: str) -> Step:
        return next(s for s in self.steps if s.id == step_id)

    def update(self, step_id: str, status: StepStatus, detail: str = "") -> None:
        with self._lock:
            step = self.step(step_id)
            step.status = status
            step.detail = detail

    def set_result(self, key: str, value) -> None:
        with self._lock:
            self.result[key] = value

    def note(self, message: str) -> None:
        with self._lock:
            if not self.notes or self.notes[-1] != message:
                self.notes.append(message)

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "id": self.id,
                "form": self.form.model_dump(),
                "started_at": self.started_at,
                "status": self.status,
                "steps": [asdict(s) for s in self.steps],
                "notes": list(self.notes),
                "error": self.error,
                "result": json.loads(json.dumps(self.result)),
            }


class SearchStopped(Exception):
    pass


class SearchManager:
    """Keeps track of the current search. One per running Jobcu."""

    def __init__(self, runner: Callable[[SearchRun], None] | None = None) -> None:
        self._lock = threading.Lock()
        self._current: SearchRun | None = None
        self._runner = runner or run_search

    @property
    def current(self) -> SearchRun | None:
        return self._current

    def start(self, form: SearchForm) -> SearchRun:
        with self._lock:
            if self._current is not None and self._current.status == "running":
                raise RuntimeError("A search is already running.")
            with db.connect() as conn:
                cursor = conn.execute(
                    "INSERT INTO searches (status, form_json) VALUES ('running', ?)",
                    (form.model_dump_json(),),
                )
                search_id = cursor.lastrowid
            run = SearchRun(
                id=search_id, form=form, started_at=datetime.now(UTC).isoformat(timespec="seconds")
            )
            self._current = run
        threading.Thread(target=self._run, args=(run,), daemon=True, name="search").start()
        return run

    def _run(self, run: SearchRun) -> None:
        try:
            self._runner(run)
            run.status = "finished"
        except SearchStopped:
            run.status = "stopped"
            _mark_remaining(run, "skipped")
        except (AIError, DocumentError) as exc:
            run.status = "failed"
            run.error = getattr(exc, "message", None) or str(exc)
            log.warning("Search %s failed: %s", run.id, getattr(exc, "detail", "") or run.error)
        except Exception:  # a bug: keep Jobcu running and tell the user plainly
            log.exception("Search %s failed unexpectedly", run.id)
            run.status = "failed"
            run.error = "Something went wrong in Jobcu. Please try again."
        finally:
            _mark_remaining(run, "failed" if run.status == "failed" else "skipped")
            with db.connect() as conn:
                conn.execute(
                    "UPDATE searches SET status = ?, finished_at = ? WHERE id = ?",
                    (run.status, datetime.now(UTC).isoformat(timespec="seconds"), run.id),
                )

    def stop(self, search_id: int) -> bool:
        run = self._current
        if run is None or run.id != search_id or run.status != "running":
            return False
        run.stop_requested = True
        run.note("Stopping after the current step…")
        return True


def _mark_remaining(run: SearchRun, status: StepStatus) -> None:
    for step in run.steps:
        if step.status == "running":
            run.update(step.id, status)
        elif step.status == "waiting":
            run.update(step.id, "skipped")


def run_search(run: SearchRun) -> None:
    """The search steps, in order."""
    settings = load_settings()
    client = AIClient(
        settings, KeyStore(), usage_log=UsageLog(), search_id=run.id, notify=run.note
    )

    def checkpoint() -> None:
        if run.stop_requested:
            raise SearchStopped

    run.update("documents", "running")
    cv_text = documents.read_text("cv")
    cover_letter_text = documents.read_text("cover_letter")
    run.update("documents", "done")
    checkpoint()

    run.update("profile", "running")
    profile = read_profile(client, cv_text, cover_letter_text)
    run.set_result("profile", profile.model_dump())
    run.update("profile", "done", profile.current_or_last_role or profile.field)
    checkpoint()

    run.update("location", "running")
    plan = interpret_location(client, run.form.location_text)
    run.set_result("location", plan.model_dump())
    names = [COUNTRIES[code].name for code in plan.countries]
    detail = f"{len(names)} countries" if plan.broad else ", ".join(names)
    run.update("location", "done", detail)
    checkpoint()

    run.update("search_words", "running")
    languages = languages_for(plan.countries)
    terms = generate_search_words(client, profile, languages)
    run.set_result("search_words", [term.model_dump() for term in terms])
    run.set_result("languages", [{"code": c, "name": LANGUAGE_NAMES[c]} for c in languages])
    run.set_result("country_names", names)
    run.update("search_words", "done", f"{len(terms)} search words in {len(languages)} languages")
    checkpoint()

    run.update("sources", "skipped", "Job sources are being connected in the next part of Phase 1")
    usage = UsageLog().for_search(run.id)
    run.set_result("usage", {step: asdict(used) for step, used in usage.items()})


manager = SearchManager()
