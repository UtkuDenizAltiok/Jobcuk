"""The job-finding part of a search: collecting from sources, duplicates, filters, full ads,
scoring and the result cards. search.py runs these steps and reports progress."""

import logging
import threading
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict

from jobcu import jobstore, travel
from jobcu.countries import COUNTRIES
from jobcu.dedupe import JobGroup, group_duplicates, is_agency
from jobcu.filters import condition_fit
from jobcu.freshness import freshness, window_start
from jobcu.jobstore import JobState
from jobcu.location import LocationPlan
from jobcu.placenames import countries_in
from jobcu.sources import all_sources
from jobcu.sources.base import (
    FoundJob,
    JobQuery,
    JobSource,
    SourceContext,
    SourceError,
    SourceReport,
)
from jobcu.sources.http import Blocked, PoliteClient

log = logging.getLogger(__name__)


class Collected:
    def __init__(self, jobs, reports, sources):
        self.jobs: list[FoundJob] = jobs
        self.reports: list[SourceReport] = reports
        self.sources: dict[str, JobSource] = sources


def collect(query: JobQuery, http: PoliteClient, keys, disabled: list[str], run) -> Collected:
    """Ask every source at the same time. A failing source never stops the others."""
    sources = all_sources()
    reports: list[SourceReport] = []
    active: list[tuple[JobSource, SourceReport]] = []
    for source in sources:
        report = SourceReport(source.id, source.name)
        reports.append(report)
        if source.id in disabled:
            report.status, report.message = "skipped", "Switched off in Settings."
        elif not source.covers(query):
            report.status, report.message = "skipped", "Doesn't cover the countries searched."
        elif reason := source.unavailable_reason(keys):
            report.status, report.message = "unavailable", reason
        else:
            active.append((source, report))

    found: dict[str, list[FoundJob]] = {}

    def progress() -> None:
        run.update("sources", "running", " · ".join(f"{r.name}: {r.jobs_found}" for _, r in active))

    def run_one(source: JobSource, report: SourceReport) -> None:
        ctx = SourceContext(http, keys, report, lambda: run.stop_requested, run.note)
        jobs: list[FoundJob] = []
        try:
            for job in source.search(query, ctx):
                jobs.append(job)
                report.jobs_found = len(jobs)
                if len(jobs) % 10 == 0:
                    progress()
        except Blocked:
            report.status = "unavailable"
            report.message = "Refused Jobcu's requests right now, so it was skipped."
        except SourceError as exc:
            report.status, report.message = "failed", str(exc)
        except Exception:
            log.exception("Source %s failed", source.id)
            report.status, report.message = "failed", "Had an unexpected problem."
        report.jobs_found = len(jobs)
        found[source.id] = jobs
        progress()

    if active:
        with ThreadPoolExecutor(max_workers=len(active), thread_name_prefix="source") as pool:
            list(pool.map(lambda pair: run_one(*pair), active))
    jobs = [job for source, _ in active for job in found.get(source.id, [])]
    return Collected(jobs, reports, {s.id: s for s in sources})


def collected_again(reports: list[dict]) -> Collected:
    """An earlier search's sources, to read more full ads after that search has ended."""
    sources = all_sources()
    return Collected([], [SourceReport(**report) for report in reports],
                     {source.id: source for source in sources})


def make_groups(collected: Collected) -> list[JobGroup]:
    kinds = {source_id: source.kind for source_id, source in collected.sources.items()}
    return group_duplicates(collected.jobs, kinds)


def load_full_ads(groups, indexes, collected: Collected, http, keys, run) -> None:
    """Fetch the full ad for jobs still in the running, where only a short version is known.

    An ad downloaded in the last few days is taken from what Jobcu remembers instead
    (DECISIONS.md), which saves time and requests without ever reusing a score.
    """
    reports = {r.source: r for r in collected.reports}
    work: dict[str, list[tuple[int, int]]] = {}
    remembered = 0
    for index in indexes:
        group = groups[index]
        if group.best_description_copy.description_is_complete:
            continue
        for copy_index, copy in enumerate(group.copies):
            source = collected.sources.get(copy.source)
            if source is None or type(source).load_details is JobSource.load_details:
                continue
            known = jobstore.remembered_ad(copy)
            if known is not None:
                group.copies[copy_index] = known
                remembered += 1
            else:
                work.setdefault(copy.source, []).append((index, copy_index))
            break
    total = sum(len(items) for items in work.values())
    known_note = f", {remembered} already known" if remembered else ""
    if not total:
        run.update("details", "done", f"Nothing more to read{known_note}")
        return
    lock = threading.Lock()
    done = [0]

    def run_source(source_id: str, items: list[tuple[int, int]]) -> None:
        source = collected.sources[source_id]
        ctx = SourceContext(http, keys, reports[source_id], lambda: run.stop_requested, run.note)
        for index, copy_index in items:
            if run.stop_requested:
                return
            try:
                full = source.load_details(groups[index].copies[copy_index], ctx)
                groups[index].copies[copy_index] = full
                jobstore.remember_ad(full)
            except Exception:
                log.exception("Reading a full ad from %s failed", source_id)
            with lock:
                done[0] += 1
                if done[0] % 5 == 0 or done[0] == total:
                    run.update("details", "running", f"{done[0]} of {total} ads{known_note}")

    with ThreadPoolExecutor(max_workers=len(work), thread_name_prefix="details") as pool:
        list(pool.map(lambda pair: run_source(*pair), work.items()))


def newest_first(groups: list[JobGroup], indexes: list[int]) -> list[int]:
    def key(index: int):
        posted = groups[index].posted_at
        return (posted is None, -(posted.timestamp() if posted else 0))

    return sorted(indexes, key=key)


def build_card(
    group: JobGroup,
    *,
    job_id: int,
    is_new: bool,
    state: JobState | None,
    scored: dict | None,
    plan: LocationPlan,
    source_names: dict[str, str],
    possible_duplicate_of: int | None,
    started_at,
    posted_within_hours: int,
) -> dict:
    main = group.main
    best = group.best_description_copy
    stated_types = sorted({t for c in group.copies for t in c.job_types})
    job_types = stated_types or ([scored["job_type"]] if scored and scored["job_type"] else [])
    work_mode = next((c.work_mode for c in group.copies if c.work_mode), None) or (
        scored or {}
    ).get("work_mode")
    # The employer's own page comes first (HANDOVER section 10), when a source led to it and
    # the ad isn't from a staffing agency.
    employer_copy = next(
        (c for c in group.copies if c.employer_url and not is_agency(c.company)), None
    )
    main_link = {"source": source_names.get(main.source, main.source), "url": main.url}
    also_on, seen = [], {main.source}
    if employer_copy is not None:
        main_link = {"source": "Employer's site", "url": employer_copy.employer_url}
        seen = set()
    # "Also on" lists other sites; repeats of the ad on the same site are left out.
    for copy in group.copies:
        if copy.source not in seen and copy.url and copy.url != main_link["url"]:
            seen.add(copy.source)
            also_on.append({"source": source_names.get(copy.source, copy.source), "url": copy.url})
    country = main.country or next((c.country for c in group.copies if c.country), None)
    checks = []
    if country and country in plan.countries:
        checks.append({
            "label": f"In {COUNTRIES[country].name}" if country in COUNTRIES else country,
            "status": "verified",
            "source": source_names.get(main.source, main.source),
        })
    elif not country:
        checks.append({"label": "Location unclear", "status": "unclear", "source": None})
    # What the conditions the person wrote say about this job (HANDOVER section 6). When its town
    # isn't known, one line says so instead of one "couldn't be checked" per condition.
    town_known = travel.job_point(group) is not None
    unanswered = 0
    for condition in plan.conditions:
        if not condition.filters:
            continue
        answer = condition_fit(condition, group)
        if answer == "unknown" and not town_known:
            unanswered += 1
            continue
        found = travel.detail(condition, group)
        checks.append({
            "label": condition.understood_as,
            "status": {"yes": "verified", "unknown": "unclear"}.get(answer, "fails"),
            "source": _checked_by(condition, found[1] if found else None),
            "detail": found[0] if found else None,
        })
    if unanswered:
        where = next((c.location_text for c in group.copies
                      if c.location_text and not countries_in(c.location_text)), None)
        conditions = "your condition about places" if unanswered == 1 else (
            "your conditions about places")
        checks.append({
            "label": (f"Jobcu doesn't know where \"{where}\" is, so {conditions} couldn't be "
                      "checked" if where else
                      f"{source_names.get(main.source, main.source)} doesn't say which town "
                      f"this job is in, nor does its text, so {conditions} couldn't be checked"),
            "status": "unclear", "source": None, "detail": None, "whole_sentence": True,
        })
    start = window_start(started_at, posted_within_hours)
    state = state or JobState()
    return {
        "job_id": job_id,
        "is_new": is_new,
        "state": asdict(state),
        "title": main.title,
        "company": main.company,
        # A town the ad's text names, when its job sites gave only a country (relevance.py).
        "location": ", ".join(group.place_from_text or []) or main.location_text,
        "location_from_ad_text": bool(group.place_from_text),
        "country": country,
        "work_mode": work_mode,
        "job_types": job_types,
        "job_types_from_ad_text": not stated_types and bool(job_types),
        "posted_at": group.posted_at.isoformat() if group.posted_at else None,
        "date_precision": group.date_precision,
        "date_known": freshness(group.posted_at, group.date_precision, start) != "unknown",
        "score": scored["score"] if scored else None,
        "parts": scored["parts"] if scored else None,
        "reasons": scored["reasons"] if scored else [],
        "required_languages": scored["required_languages"] if scored else [],
        "main_link": main_link,
        "also_on": also_on,
        "possible_duplicate_of": possible_duplicate_of,
        "summary_only": not best.description_is_complete,
        "salary": best.salary_text or main.salary_text,
        "location_checks": checks,
    }


def _checked_by(condition, measured_by: str | None = None) -> str:
    if measured_by == "AI estimate":
        return "AI estimate"
    if measured_by == "Google Maps":
        return "Google Maps"
    if condition.changed_by_you:
        return "Changed by you"
    if condition.status == "estimate" and measured_by is None:
        return "AI estimate"
    if condition.kind in ("town_size", "near"):
        return "Worked out by Jobcu"
    return "Checked on the web"


def sort_cards(cards: list[dict]) -> list[dict]:
    """Highest score first; newer first when scores are equal (HANDOVER section 12)."""
    return sorted(
        cards,
        key=lambda c: (
            c["score"] is None,
            -(c["score"] or 0),
            -(_timestamp(c["posted_at"])),
        ),
    )


def _timestamp(iso: str | None) -> float:
    from jobcu.freshness import parse_iso

    parsed = parse_iso(iso)
    return parsed.timestamp() if parsed else 0.0


def unique_counts(groups: list[JobGroup], shown: list[int]) -> Counter:
    """Jobs found only by one source, per source (HANDOVER section 9.0, point 6)."""
    counts: Counter = Counter()
    for index in shown:
        sources = {copy.source for copy in groups[index].copies}
        if len(sources) == 1:
            counts[next(iter(sources))] += 1
    return counts
