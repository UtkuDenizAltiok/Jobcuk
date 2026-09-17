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

from jobcu import db, documents, jobstore, pipeline, quality
from jobcu.ai.base import AIError
from jobcu.ai.client import AIClient
from jobcu.ai.usage import UsageLog
from jobcu.countries import COUNTRIES, LANGUAGE_NAMES, languages_for
from jobcu.documents import DocumentError
from jobcu.filters import REASONS, apply_rules
from jobcu.keystore import KeyStore
from jobcu.keywords import generate_search_words
from jobcu.location import interpret_location
from jobcu.profile import read_profile_reusing
from jobcu.relevance import quick_pass
from jobcu.scoring import score_groups
from jobcu.settings import SearchForm, load_settings
from jobcu.sources.base import JobQuery
from jobcu.sources.http import PoliteClient

log = logging.getLogger(__name__)

StepStatus = Literal["waiting", "running", "done", "failed", "skipped"]
RunStatus = Literal["running", "finished", "failed", "stopped"]

STEPS: list[tuple[str, str]] = [
    ("documents", "Reading your CV and cover letter"),
    ("profile", "Understanding your profile"),
    ("location", "Understanding where you want to work"),
    ("search_words", "Preparing search words"),
    ("sources", "Searching job sources"),
    ("filtering", "Removing duplicates and jobs that don't fit"),
    ("details", "Reading the full job ads"),
    ("scoring", "Scoring jobs"),
]

# How long a search waits for an answer to a question (e.g. the scoring limit) before
# carrying on without the extra work.
QUESTION_TIMEOUT_SECONDS = 3600


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
    question: dict | None = None
    _answer: bool = False
    _answered: threading.Event = field(default_factory=threading.Event, repr=False)
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

    def ask(self, question: dict) -> bool:
        """Show a yes/no question on the screen and wait for the answer."""
        with self._lock:
            self.question = question
            self._answered.clear()
        answered = self._answered.wait(QUESTION_TIMEOUT_SECONDS)
        with self._lock:
            self.question = None
            return answered and self._answer and not self.stop_requested

    def answer(self, value: bool) -> bool:
        with self._lock:
            if self.question is None:
                return False
            self._answer = value
        self._answered.set()
        return True

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
                "question": self.question,
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
            if "jobs" in run.result:
                # Kept so the results are still there after Jobcu restarts.
                jobstore.save_results(run.id, json.dumps(run.snapshot()))
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
        run.answer(False)
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
    profile, reused = read_profile_reusing(client, cv_text, cover_letter_text)
    run.set_result("profile", profile.model_dump())
    detail = profile.current_or_last_role or profile.field
    run.update("profile", "done", f"{detail} (documents unchanged, read again not needed)"
               if reused else detail)
    checkpoint()

    run.update("location", "running")
    plan = interpret_location(client, run.form.location_text)
    run.set_result("location", plan.model_dump())
    names = [COUNTRIES[code].name for code in plan.countries]
    detail = f"{len(names)} countries" if plan.broad else ", ".join(names)
    run.update("location", "done", detail)
    checkpoint()

    run.update("search_words", "running")
    languages = languages_for(plan.countries, plan.places)
    terms = generate_search_words(client, profile, languages)
    run.set_result("search_words", [term.model_dump() for term in terms])
    run.set_result("languages", [{"code": c, "name": LANGUAGE_NAMES[c]} for c in languages])
    run.set_result("country_names", names)
    run.update("search_words", "done", f"{len(terms)} search words in {len(languages)} languages")
    checkpoint()

    keys = KeyStore()
    started_at = datetime.fromisoformat(run.started_at)
    query = JobQuery(
        countries=plan.countries,
        places=plan.places,
        terms=terms,
        posted_within_hours=run.form.posted_within_hours,
        started_at=started_at,
    )
    http = PoliteClient()
    try:
        _find_and_score(run, settings, client, keys, http, profile, plan, query, checkpoint)
    finally:
        http.close()
        usage = UsageLog().for_search(run.id)
        run.set_result("usage", {step: asdict(used) for step, used in usage.items()})


def _find_and_score(run, settings, client, keys, http, profile, plan, query, checkpoint) -> None:
    form = run.form
    run.update("sources", "running")
    collected = pipeline.collect(query, http, keys, settings.sources_disabled, run)
    names = {source_id: source.name for source_id, source in collected.sources.items()}
    working = [r for r in collected.reports if r.status in ("ok", "partial")]
    run.update("sources", "done" if working else "failed", f"{len(collected.jobs)} job ads found")
    for report in collected.reports:
        if report.message and report.status in ("partial", "failed", "unavailable"):
            run.note(report.message if report.message.startswith(report.name)
                     else f"{report.name}: {report.message}")
    checkpoint()

    run.update("filtering", "running")
    groups = pipeline.make_groups(collected)
    remembered = jobstore.find_job_ids(groups)
    states = jobstore.states([job_id for job_id in remembered if job_id])
    remembered_states = [states.get(job_id) if job_id else None for job_id in remembered]
    outcome = apply_rules(
        groups,
        remembered_states,
        started_at=query.started_at,
        posted_within_hours=form.posted_within_hours,
        job_types=form.job_types,
        exclude_remote=form.exclude_remote,
        countries=plan.countries,
    )
    left_out = dict(outcome.left_out)
    unrelated = set(quick_pass(client, profile, groups, outcome.kept)) if outcome.kept else set()
    candidates = [i for i in outcome.kept if i not in unrelated]
    run.update(
        "filtering",
        "done",
        f"{len(groups)} different jobs, {len(candidates)} worth a closer look",
    )
    checkpoint()

    run.update("details", "running")
    pipeline.load_full_ads(groups, candidates, collected, http, keys, run)
    run.update("details", "done", "Full ads read where available")
    checkpoint()

    run.update("scoring", "running")
    order = pipeline.newest_first(groups, candidates)
    cap = settings.limits.scoring_cap
    scored: dict[int, dict] = {}
    position = 0
    while position < len(order):
        chunk = order[position : position + cap] if position == 0 else order[position:]
        if position > 0:
            remaining = len(order) - position
            wants_more = run.ask({
                "kind": "scoring_cap",
                "message": (
                    f"Jobcu has scored {position} jobs, the limit you set for one search. "
                    f"{remaining} more jobs are waiting. Score them too? This uses more AI."
                ),
                "yes": f"Score {remaining} more",
                "no": "Show results now",
            })
            if not wants_more:
                break
            chunk = order[position : position + cap]

        def progress(done, total, base=position):
            run.update("scoring", "running", f"{base + done} of {len(order)} jobs")

        scored.update(score_groups(client, profile, plan, groups, chunk, on_progress=progress))
        position += len(chunk)
        checkpoint()

    # Facts only the ad text revealed can still rule a job out.
    shown: list[int] = []
    for index in candidates:
        result = scored.get(index)
        stated_types = any(copy.job_types for copy in groups[index].copies)
        if result and form.exclude_remote and result["fully_remote"]:
            left_out["remote_text"] = left_out.get("remote_text", 0) + 1
        elif (
            result and not stated_types and result["job_type"]
            and result["job_type"] not in form.job_types
        ):
            left_out["job_type_text"] = left_out.get("job_type_text", 0) + 1
        else:
            shown.append(index)
    run.update("scoring", "done", f"{len(scored)} jobs scored")

    hidden = [i for i, s in enumerate(remembered_states) if s is not None and s.dismissed]
    to_remember = shown + hidden
    job_ids, new_flags = jobstore.remember([groups[i] for i in to_remember], run.id)
    id_of = dict(zip(to_remember, job_ids, strict=True))
    new_of = dict(zip(to_remember, new_flags, strict=True))
    states = jobstore.states(job_ids)

    def card(index: int) -> dict:
        duplicate = groups[index].possible_duplicate_of
        return pipeline.build_card(
            groups[index],
            job_id=id_of[index],
            is_new=new_of[index],
            state=states.get(id_of[index]),
            scored=scored.get(index),
            plan=plan,
            source_names=names,
            possible_duplicate_of=id_of.get(duplicate) if duplicate is not None else None,
            started_at=query.started_at,
            posted_within_hours=form.posted_within_hours,
        )

    cards = [card(i) for i in shown]
    jobstore.save_cards(cards)
    unique = pipeline.unique_counts(groups, shown)
    reasons = {**REASONS, "remote_text": "Fully remote, according to the ad text",
               "job_type_text": "A job type you didn't tick, according to the ad text"}
    run.set_result("jobs", {
        "cards": pipeline.sort_cards([c for c in cards if c["date_known"]]),
        "date_unknown": pipeline.sort_cards([c for c in cards if not c["date_known"]]),
        "hidden": [card(i) for i in hidden],
        "new_count": sum(1 for c in cards if c["is_new"]),
        "counts": {
            "ads_found": len(collected.jobs),
            "different_jobs": len(groups),
            "left_out": [{"reason": reasons[k], "count": v} for k, v in left_out.items()],
            "unrelated": len(unrelated),
            "unrelated_titles": sorted({groups[i].main.title for i in unrelated})[:200],
            "not_scored": len(candidates) - len(scored),
            "shown": len(cards),
        },
        "sources": [
            {**asdict(r), "unique": unique.get(r.source, 0)} for r in collected.reports
        ],
    })
    _keep_for_the_score_check(groups, shown, scored, unrelated)


def _keep_for_the_score_check(groups, shown, scored, unrelated) -> None:
    """Keeps a few of this search's real ads and left-out titles for the score check
    (HANDOVER section 13). It costs nothing: everything is already in hand."""
    ads = []
    for index in shown:
        best = groups[index].best_description_copy
        if not best.description_is_complete:
            continue
        ads.append({
            "source": best.source, "source_job_id": best.source_job_id, "title": best.title,
            "company": best.company, "location": best.location_text, "url": best.url,
            "score": (scored.get(index) or {}).get("score"), "text": best.description,
        })
    titles = [
        {"source": groups[i].main.source, "source_job_id": groups[i].main.source_job_id,
         "title": groups[i].main.title, "company": groups[i].main.company,
         "location": groups[i].main.location_text, "url": groups[i].main.url}
        for i in sorted(unrelated)
    ]
    try:
        quality.collect_from_search(ads, titles)
    except Exception:  # the score check is a helper, never a reason for a search to fail
        log.exception("Keeping ads for the score check failed")


manager = SearchManager()
