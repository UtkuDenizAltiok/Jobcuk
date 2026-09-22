"""Runs a search in the background and reports its progress (HANDOVER sections 3 and 9).

A search is a list of steps. Each step updates what the screen shows, so the user
can see what Jobcu is doing. Only one search runs at a time. Every search starts
fresh from the current CV, cover letter and location text.
"""

import dataclasses
import json
import logging
import threading
from collections import Counter
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Literal

from jobcu import db, documents, jobplace, jobstore, pipeline, quality, travel
from jobcu import pool as search_pool
from jobcu.ai.base import AIError
from jobcu.ai.client import AIClient
from jobcu.ai.usage import UsageLog
from jobcu.countries import COUNTRIES, LANGUAGE_NAMES, languages_for
from jobcu.documents import DocumentError
from jobcu.filters import REASONS, apply_rules, fails_a_condition
from jobcu.keystore import KeyStore
from jobcu.keywords import generate_search_words
from jobcu.location import (
    ConditionEdit,
    LocationPlan,
    apply_edits,
    check_edits,
    interpret_location,
    needs_checking,
)
from jobcu.profile import Profile, read_profile_reusing
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
    ("places", "Finding where the best jobs are"),
]
# Applying corrected conditions to the jobs a search already found (HANDOVER section 6, "Edit").
REAPPLY_STEPS: list[tuple[str, str]] = [
    ("conditions", "Checking the conditions you changed"),
    ("filtering", "Applying your conditions to the jobs found"),
    ("details", "Reading the full job ads"),
    ("scoring", "Scoring jobs that came back in"),
    ("places", "Finding where the best jobs are"),
]

# How long a search waits for an answer to a question (e.g. the scoring limit) before
# carrying on without the extra work.
QUESTION_TIMEOUT_SECONDS = 3600
# How many jobs ruled out by a condition the person wrote are listed back to them.
MAX_RULED_OUT_SHOWN = 60


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
    kind: Literal["search", "reapply"] = "search"
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
                "kind": self.kind,
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
        threading.Thread(
            target=self._run, args=(run, self._runner), daemon=True, name="search"
        ).start()
        return run

    def reapply(self, search_id: int, edits: list[ConditionEdit]) -> SearchRun:
        """Applies corrected conditions to the jobs the latest search found, in the background.

        Raises LookupError when those jobs aren't kept any more, and EditProblem when the
        corrections can't be used."""
        with self._lock:
            current = self._current
            if current is not None and current.status == "running":
                raise RuntimeError("A search is already running.")
            if current is not None and current.id == search_id:
                snapshot = current.snapshot()
            else:
                saved = jobstore.latest_results()
                snapshot = json.loads(saved[1]) if saved and saved[0] == search_id else None
            job_pool = search_pool.load(search_id) if snapshot else None
            if job_pool is None or not {"jobs", "location"} <= set(snapshot["result"]):
                raise LookupError(search_id)
            check_edits(LocationPlan.model_validate(snapshot["result"]["location"]), edits)
            run = SearchRun(
                id=search_id,
                form=SearchForm.model_validate(snapshot["form"]),
                started_at=snapshot["started_at"],
                kind="reapply",
                steps=[Step(i, label) for i, label in REAPPLY_STEPS],
                result=snapshot["result"],
            )
            self._current = run
        threading.Thread(
            target=self._run,
            args=(run, lambda run: reapply_conditions(run, job_pool, edits)),
            daemon=True,
            name="search",
        ).start()
        return run

    def _run(self, run: SearchRun, runner: Callable[[SearchRun], None]) -> None:
        try:
            runner(run)
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
        _checkpoint(run)

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

    run.update("location", "running", "Reading what you wrote")
    plan = interpret_location(client, run.form.location_text)
    run.set_result("location", plan.model_dump())
    names = [COUNTRIES[code].name for code in plan.countries]
    detail = f"{len(names)} countries" if plan.broad else ", ".join(names)
    checked = sum(1 for c in plan.conditions if c.status in ("applied", "estimate"))
    if checked:
        detail += f" · {checked} condition{'s' if checked > 1 else ''} checked"
    run.update("location", "done", detail)
    for condition in plan.conditions:
        if condition.status == "not_checked" and condition.kind != "about_job":
            run.note(f"\"{condition.text}\": {condition.note}")
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
    hidden = [i for i, s in enumerate(remembered_states) if s is not None and s.dismissed]
    hidden_ids, hidden_new = jobstore.remember([groups[i] for i in hidden], run.id)
    hidden_states = jobstore.states(hidden_ids)
    hidden_cards = [
        pipeline.build_card(
            groups[index], job_id=job_id, is_new=is_new, state=hidden_states.get(job_id),
            scored=None, plan=plan, source_names=names, possible_duplicate_of=None,
            started_at=query.started_at, posted_within_hours=form.posted_within_hours,
        )
        for index, job_id, is_new in zip(hidden, hidden_ids, hidden_new, strict=True)
    ]
    # Every job that passed these rules is kept together with what the search learns about it:
    # the conditions about places decide the rest, and the person may correct those later.
    position = {index: n for n, index in enumerate(outcome.kept)}
    job_pool = search_pool.Pool(
        search_id=run.id,
        jobs=[
            search_pool.PoolJob(dataclasses.replace(
                group, possible_duplicate_of=position.get(group.possible_duplicate_of)
            ))
            for group in (groups[index] for index in outcome.kept)
        ],
        profile=profile.model_dump(),
        left_out=dict(outcome.left_out),
        source_names=names,
        ads_found=len(collected.jobs),
        different_jobs=len(groups),
    )
    _decide(run, client, keys, http, settings, plan, job_pool, collected, hidden_cards, checkpoint)


def _decide(run, client, keys, http, settings, plan, job_pool, collected, hidden_cards,
            checkpoint) -> None:
    """Applies the conditions about places to the kept jobs, then checks, reads and scores the
    ones still in the running, and builds the results.

    A search does this once. Correcting the conditions afterwards does it again for the same
    jobs, reusing every answer already worked out, so only jobs that come back in cost AI.
    """
    form = run.form
    started_at = datetime.fromisoformat(run.started_at)
    profile = Profile.model_validate(job_pool.profile)
    groups = [job.group for job in job_pool.jobs]
    # Travel times cost a request each, so they're measured last, only for jobs still worth a
    # closer look; everything else about places is worked out at once.
    measured = [c for c in plan.conditions if c.kind == "near" and c.max_minutes and c.filters]
    at_once = [c for c in plan.conditions if all(c is not m for m in measured)]
    ruled_out = [i for i, group in enumerate(groups) if fails_a_condition(group, at_once)]
    excluded = set(ruled_out)
    in_running = [i for i in range(len(groups)) if i not in excluded]
    unchecked = [i for i in in_running if job_pool.jobs[i].unrelated is None]
    if unchecked:
        checked = quick_pass(client, profile, groups, unchecked)
        for index in unchecked:
            job_pool.jobs[index].unrelated = index in checked.unrelated
        for index, places in checked.places.items():
            groups[index].place_from_text = places
        # Where the ad's text named the town, the conditions about places can decide now.
        placed = [i for i, places in checked.places.items() if places]
        newly_out = [i for i in placed if fails_a_condition(groups[i], at_once)]
        ruled_out = sorted([*ruled_out, *newly_out])
        in_running = [i for i in in_running if i not in set(newly_out)]
    unrelated = [i for i in in_running if job_pool.jobs[i].unrelated]
    candidates = [i for i in in_running if not job_pool.jobs[i].unrelated]
    if measured and candidates:
        run.update("filtering", "running", "Measuring travel times")
        if not keys.get(travel.KEY_NAME):
            run.note("Travel times are AI estimates. A Google Maps key in Settings gives real "
                     "ones.")
        travel.TravelMeter(client, keys, http, settings, note=run.note).measure(
            measured, groups, candidates)
        too_far = {i for i in candidates if fails_a_condition(groups[i], measured)}
        candidates = [i for i in candidates if i not in too_far]
        ruled_out += sorted(too_far)
    run.update(
        "filtering",
        "done",
        f"{job_pool.different_jobs} different jobs, {len(candidates)} worth a closer look",
    )
    checkpoint()

    to_score = [i for i in candidates if job_pool.jobs[i].scored is None]
    run.update("details", "running")
    pipeline.load_full_ads(groups, to_score, collected, http, keys, run)
    run.update("details", "done", "Full ads read where available")
    checkpoint()

    run.update("scoring", "running")
    order = pipeline.newest_first(groups, to_score)
    cap = settings.limits.scoring_cap
    scored_now: dict[int, dict] = {}
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

        scored_now.update(score_groups(client, profile, plan, groups, chunk, on_progress=progress))
        position += len(chunk)
        checkpoint()
    for index, result in scored_now.items():
        job_pool.jobs[index].scored = result
    nothing_new = not scored_now and run.kind == "reapply"
    run.update("scoring", "done",
               "Nothing new to score" if nothing_new else f"{len(scored_now)} jobs scored")
    checkpoint()

    # The best jobs whose town nobody gave: the person's AI finds their ads online, and the
    # conditions about places then decide about them too.
    run.update("places", "running")
    worth_it = sorted(
        (i for i in candidates if jobplace.needs_looking_up(groups[i])
         and (job_pool.jobs[i].scored or {}).get("score", 0) >= jobplace.MIN_SCORE),
        key=lambda i: -job_pool.jobs[i].scored["score"])
    found = jobplace.find_online(client, groups, worth_it) if worth_it else 0
    placed = [i for i in worth_it if groups[i].place_from_web]
    fails = [i for i in placed if fails_a_condition(groups[i], at_once)]
    if measured and placed:
        in_reach = [i for i in placed if i not in fails]
        travel.TravelMeter(client, keys, http, settings, note=run.note).measure(
            measured, groups, in_reach)
        fails += [i for i in in_reach if fails_a_condition(groups[i], measured)]
    ruled_out = sorted([*ruled_out, *fails])
    candidates = [i for i in candidates if i not in set(fails)]
    run.update("places", "done", f"Found online for {found} of {len(worth_it)} jobs"
               if worth_it else "Every job worth showing has a known town")

    # Facts only the ad text revealed can still rule a job out.
    left_out = Counter(job_pool.left_out)
    if ruled_out:
        left_out["location_condition"] = len(ruled_out)
    shown: list[int] = []
    for index in candidates:
        result = job_pool.jobs[index].scored
        stated_types = any(copy.job_types for copy in groups[index].copies)
        if result and form.exclude_remote and result["fully_remote"]:
            left_out["remote_text"] += 1
        elif (
            result and not stated_types and result["job_type"]
            and result["job_type"] not in form.job_types
        ):
            left_out["job_type_text"] += 1
        else:
            shown.append(index)

    job_ids, new_flags = jobstore.remember([groups[i] for i in shown], run.id)
    id_of = dict(zip(shown, job_ids, strict=True))
    new_of = dict(zip(shown, new_flags, strict=True))
    states = jobstore.states(job_ids)
    names = job_pool.source_names

    def card(index: int) -> dict:
        duplicate = groups[index].possible_duplicate_of
        return pipeline.build_card(
            groups[index],
            job_id=id_of[index],
            is_new=new_of[index],
            state=states.get(id_of[index]),
            scored=job_pool.jobs[index].scored,
            plan=plan,
            source_names=names,
            possible_duplicate_of=id_of.get(duplicate) if duplicate is not None else None,
            started_at=started_at,
            posted_within_hours=form.posted_within_hours,
        )

    cards = [card(i) for i in shown]
    # Jobs a condition the person wrote ruled out are listed (without scores), so they can see
    # what the condition did and judge whether the AI read it right.
    ruled_out_cards = [
        pipeline.build_card(
            groups[index], job_id=0, is_new=False, state=None, scored=None, plan=plan,
            source_names=names, possible_duplicate_of=None, started_at=started_at,
            posted_within_hours=form.posted_within_hours,
        )
        for index in ruled_out[:MAX_RULED_OUT_SHOWN]
    ]
    jobstore.save_cards(cards)
    job_pool.reports = [asdict(report) for report in collected.reports]
    unique = pipeline.unique_counts(groups, shown)
    reasons = {**REASONS, "remote_text": "Fully remote, according to the ad text",
               "job_type_text": "A job type you didn't tick, according to the ad text"}
    run.set_result("location", plan.model_dump())
    run.set_result("jobs", {
        "cards": pipeline.sort_cards([c for c in cards if c["date_known"]]),
        "date_unknown": pipeline.sort_cards([c for c in cards if not c["date_known"]]),
        "hidden": hidden_cards,
        "ruled_out_by_conditions": ruled_out_cards,
        "new_count": sum(1 for c in cards if c["is_new"]),
        "counts": {
            "ads_found": job_pool.ads_found,
            "different_jobs": job_pool.different_jobs,
            "left_out": [{"reason": reasons[k], "count": v} for k, v in left_out.items() if v],
            "unrelated": len(unrelated),
            "unrelated_titles": sorted({groups[i].main.title for i in unrelated})[:200],
            "not_scored": sum(1 for i in candidates if job_pool.jobs[i].scored is None),
            "shown": len(cards),
        },
        "sources": [
            {**report, "unique": unique.get(report["source"], 0)} for report in job_pool.reports
        ],
    })
    search_pool.save(job_pool)
    # Only what this pass worked out is new for the score check.
    worked_on = set(unchecked) | set(scored_now)
    _keep_for_the_score_check(
        groups,
        [i for i in shown if i in worked_on],
        scored_now,
        {i for i in unrelated if i in worked_on},
    )


def reapply_conditions(run: SearchRun, job_pool: search_pool.Pool,
                       edits: list[ConditionEdit]) -> None:
    """The person corrected the conditions after a search: check what they reworded, then
    decide again about the jobs that search found (HANDOVER section 6, "Edit")."""
    settings = load_settings()
    client = AIClient(
        settings, KeyStore(), usage_log=UsageLog(), search_id=run.id, notify=run.note
    )
    run.update("conditions", "running")
    plan = LocationPlan.model_validate(run.result["location"])
    rechecked = sum(1 for edit in edits if needs_checking(edit, plan.conditions))
    plan = apply_edits(client, plan, edits)
    run.update("conditions", "done", f"{rechecked} checked again" if rechecked
               else "Nothing to look up")
    for condition in plan.conditions:
        if condition.status == "not_checked" and condition.kind != "about_job":
            run.note(f"\"{condition.text}\": {condition.note}")
    _checkpoint(run)

    http = PoliteClient()
    try:
        collected = pipeline.collected_again(job_pool.reports)
        _decide(run, client, KeyStore(), http, settings, plan, job_pool, collected,
                run.result["jobs"]["hidden"], lambda: _checkpoint(run))
    finally:
        http.close()
        usage = UsageLog().for_search(run.id)
        run.set_result("usage", {step: asdict(used) for step, used in usage.items()})


def _checkpoint(run: SearchRun) -> None:
    if run.stop_requested:
        raise SearchStopped


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
