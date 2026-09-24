"""Teaching Vacancies: England's official service for jobs in schools (Department for
Education), checked 2026-09-24.

An open API lists every live job (about 6,800; some 230 new on a weekday), 100 a page, newest
first, in the standard job format (schema.org JobPosting). Teachers, teaching assistants,
school leaders, office, catering, cleaning and site staff. The listings may be reused under
the Open Government Licence (the terms for API users add only that nobody may charge a fee for
hiring someone found through them).

The API's text is the ad's first part. The job's own page adds what matters most for deciding
(whether a visa can be sponsored, the contract, the pay scale, the closing date), so the page
is read for the jobs still in the running.
"""

import dataclasses
import re
from collections.abc import Iterator
from datetime import date

import httpx
import trafilatura

from jobcu.freshness import day_at_utc, freshness, window_start
from jobcu.sources.base import FoundJob, JobQuery, JobSource, SourceContext, SourceError
from jobcu.sources.budget import BudgetExhausted, Limits, RequestBudget
from jobcu.sources.http import Blocked
from jobcu.sources.matching import matches_places, matches_terms
from jobcu.text import html_to_text, tidy

API = "https://teaching-vacancies.service.gov.uk/api/v1/jobs.json"
# About 230 new jobs a weekday, 100 a page: a week is about 16 pages.
LIMITS = Limits(per_search=30)


class TeachingVacanciesSource(JobSource):
    id = "teachingvacancies"
    name = "Teaching Vacancies (England's schools)"
    kind = "job_board"
    countries = frozenset({"GB"})

    def search(self, query: JobQuery, ctx: SourceContext) -> Iterator[FoundJob]:
        budget = RequestBudget(self.id, self.name, LIMITS)
        start = window_start(query.started_at, query.posted_within_hours)
        page = 1
        try:
            while not ctx.should_stop():
                items, last_page = self._page(page, budget, ctx)
                jobs = [job for job in map(to_found_job, items) if job]
                for job in jobs:
                    if freshness(job.posted_at, job.date_precision, start) == "too_old":
                        continue
                    if not matches_terms(query.terms, {"en"}, job.title, job.description):
                        continue
                    if matches_places(query.places, "GB", job.location_text):
                        yield job
                # Newest first: once a job is older than the window, every later page is too.
                if page >= last_page or not jobs or any(
                    freshness(job.posted_at, job.date_precision, start) == "too_old"
                    for job in jobs
                ):
                    return
                page += 1
        except BudgetExhausted as exc:
            ctx.report.status = "partial"
            ctx.report.message = exc.message

    def load_details(self, job: FoundJob, ctx: SourceContext) -> FoundJob:
        try:
            response = ctx.http.get(job.url)
        except (httpx.HTTPError, Blocked):
            return job
        if response.status_code != 200:
            return job
        text = tidy(trafilatura.extract(response.text, include_comments=False,
                                        include_tables=True, favor_recall=True) or "")
        if len(text) <= len(job.description):
            return job
        return dataclasses.replace(job, description=text, description_is_complete=True)

    def _page(self, page: int, budget: RequestBudget, ctx: SourceContext) -> tuple[list, int]:
        budget.spend()
        ctx.report.requests += 1
        try:
            response = ctx.http.get(API, params={"page": page}, cache=False)
        except httpx.HTTPError as exc:
            raise SourceError("Teaching Vacancies couldn't be reached.") from exc
        if response.status_code == 429:
            raise BudgetExhausted("Teaching Vacancies: asked Jobcu to slow down for now.")
        if response.status_code != 200:
            raise SourceError(
                f"Teaching Vacancies answered with a problem (code {response.status_code})."
            )
        try:
            data = response.json()
        except ValueError as exc:
            raise SourceError("Teaching Vacancies didn't answer with a job list.") from exc
        last = (data.get("meta") or {}).get("totalPages") or page
        return data.get("data") or [], int(last)


def _job_types(raw: list | str | None) -> list[str]:
    """The API's employment types. "TEMPORARY" marks a fixed-term contract, so "FULL_TIME" on
    its own is a permanent job."""
    kinds = {str(kind).upper() for kind in (raw if isinstance(raw, list) else [raw]) if kind}
    types = []
    if "TEMPORARY" in kinds:
        types.append("fixed_term")
    elif "FULL_TIME" in kinds:
        types.append("full_time_permanent")
    if "PART_TIME" in kinds:
        types.append("part_time")
    return types


def _places(value) -> tuple[str | None, str | None]:
    """The towns and the country code. A job can be at several schools of one trust."""
    towns, country = [], None
    for place in value if isinstance(value, list) else [value]:
        address = place.get("address") if isinstance(place, dict) else None
        if not isinstance(address, dict):
            continue
        town = address.get("addressLocality") or address.get("addressRegion")
        if town and town not in towns:
            towns.append(str(town))
        country = country or address.get("addressCountry")
    return ", ".join(towns) or None, country


def to_found_job(item: dict) -> FoundJob | None:
    url = str(item.get("url") or "")
    title = html_to_text(str(item.get("title") or ""))
    if not url or not title:
        return None
    location, country = _places(item.get("jobLocation"))
    try:
        posted = day_at_utc(date.fromisoformat(str(item.get("datePosted") or "")[:10]))
    except ValueError:
        posted = None
    organisation = item.get("hiringOrganization") or {}
    return FoundJob(
        source="teachingvacancies",
        source_job_id=re.sub(r"^.*/jobs/", "", url),
        url=url,
        title=title,
        company=(organisation.get("name") if isinstance(organisation, dict) else None) or None,
        location_text=location,
        country=country or "GB",
        posted_at=posted,
        date_precision="day" if posted else "unknown",
        description=html_to_text(str(item.get("description") or "")),
        job_types=_job_types(item.get("employmentType")),
    )
