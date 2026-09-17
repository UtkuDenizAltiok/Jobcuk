"""Arbeitnow: a free public job API, mostly jobs that companies posted through career systems
(Greenhouse, SmartRecruiters, JOIN, Teamtailor, Recruitee and others). Checked 2026-09-17.

`GET /api/job-board-api` returns the newest jobs with their full ad text and the exact time
they appeared; `?page=N` goes further back. arbeitnow.com covers Germany and its neighbours,
arbeitnow.co.uk the United Kingdom. No key. Its terms ask for no abuse and for a link back,
which Jobcu does by linking to the job's page there.
"""

from collections.abc import Iterator
from datetime import UTC, datetime

import httpx

from jobcu.countries import COUNTRIES
from jobcu.freshness import freshness, window_start
from jobcu.placenames import OTHER, countries_in, is_europe_wide
from jobcu.sources.base import FoundJob, JobQuery, JobSource, SourceContext, SourceError
from jobcu.sources.budget import BudgetExhausted, Limits, RequestBudget
from jobcu.sources.careers import job_types_from_text
from jobcu.sources.matching import matches_places, matches_terms
from jobcu.text import html_to_text

SITES = {"https://www.arbeitnow.com/api/job-board-api": None,
         "https://www.arbeitnow.co.uk/api/job-board-api": "GB"}
# About 200 new jobs a day per list, 100 to 250 a page, and the pages aren't strictly in date
# order, so Jobcu reads a few pages more than the window needs and stops at the first page with
# nothing fresh on it.
PAGES_PER_DAY = 4
MIN_PAGES, MAX_PAGES = 3, 20
LIMITS = Limits(per_search=60)


class ArbeitnowSource(JobSource):
    id = "arbeitnow"
    name = "Arbeitnow"
    kind = "job_board"

    def search(self, query: JobQuery, ctx: SourceContext) -> Iterator[FoundJob]:
        budget = RequestBudget(self.id, self.name, LIMITS)
        start = window_start(query.started_at, query.posted_within_hours)
        languages = {"en"}
        for code in query.countries:
            languages.update(COUNTRIES[code].ad_languages)
        pages = min(MAX_PAGES, max(MIN_PAGES,
                                   -(-query.posted_within_hours * PAGES_PER_DAY // 24)))
        seen: set[str] = set()
        try:
            for site, only_country in SITES.items():
                if only_country and only_country not in query.countries:
                    continue
                for page in range(1, pages + 1):
                    if ctx.should_stop():
                        return
                    jobs = [to_found_job(item) for item in self._page(site, page, budget, ctx)]
                    fresh = 0
                    for job in jobs:
                        if freshness(job.posted_at, job.date_precision, start) == "too_old":
                            continue
                        fresh += 1
                        if job.source_job_id in seen:
                            continue
                        seen.add(job.source_job_id)
                        country = self._country(job, query.countries)
                        if country is None and not is_europe_wide(job.location_text):
                            continue
                        job.country = country
                        if not matches_terms(query.terms, languages, job.title, job.description):
                            continue
                        if country and not matches_places(query.places, country,
                                                          job.location_text):
                            continue
                        yield job
                    if not jobs or not fresh:
                        break  # nothing inside the window on this page: the rest is older
        except BudgetExhausted as exc:
            ctx.report.status = "partial"
            ctx.report.message = exc.message

    def _country(self, job: FoundJob, searched: list[str]) -> str | None:
        found = countries_in(job.location_text) - {OTHER}
        return next((code for code in searched if code in found), None)

    def _page(self, site: str, page: int, budget, ctx: SourceContext) -> list[dict]:
        budget.spend()
        ctx.report.requests += 1
        try:
            response = ctx.http.get(site, params={"page": page})
        except httpx.HTTPError as exc:
            raise SourceError("Arbeitnow couldn't be reached.") from exc
        if response.status_code == 429:
            raise BudgetExhausted("Arbeitnow: asked Jobcu to slow down for now.")
        if response.status_code != 200:
            raise SourceError(f"Arbeitnow answered with a problem (code {response.status_code}).")
        try:
            return response.json().get("data") or []
        except ValueError as exc:
            raise SourceError("Arbeitnow didn't answer with a job list.") from exc


def to_found_job(item: dict) -> FoundJob:
    created = item.get("created_at")
    posted = datetime.fromtimestamp(created, UTC) if isinstance(created, int | float) else None
    types: list[str] = []
    for text in item.get("job_types") or []:
        types.extend(kind for kind in job_types_from_text(text) if kind not in types)
    return FoundJob(
        source="arbeitnow",
        source_job_id=str(item.get("slug")),
        url=item.get("url") or "",
        title=(item.get("title") or "").strip(),
        company=item.get("company_name") or None,
        location_text=item.get("location") or None,
        posted_at=posted,
        date_precision="exact" if posted else "unknown",
        description=html_to_text(item.get("description")),
        description_is_complete=True,
        job_types=types,
        work_mode="remote" if item.get("remote") else None,
    )
