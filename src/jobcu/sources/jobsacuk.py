"""jobs.ac.uk: jobs at universities, research institutes and related employers, mostly in the
United Kingdom and Ireland. Checked 2026-09-17.

There's no API. The search page can be sorted newest first (`sortOrder=1`), so Jobcu reads a page
per search word until the jobs are older than "Posted within". Each job's own page carries
schema.org JobPosting data, which `jobposting.py` reads for the full ad and the exact date.

robots.txt allows everything except the feedback pages, and the terms say material may be
downloaded "for your own personal use", which is exactly what Jobcu does: it shows the jobs to
the person searching and never re-publishes them.
"""

import dataclasses
import logging
import re
from collections.abc import Iterator
from datetime import date, datetime, timedelta

import httpx
from lxml import html as lxml_html
from lxml.etree import ParserError

from jobcu.freshness import day_at_utc, freshness, window_start
from jobcu.jobposting import find_job_posting
from jobcu.placenames import countries_in
from jobcu.sources.base import FoundJob, JobQuery, JobSource, SourceContext, SourceError
from jobcu.sources.budget import BudgetExhausted, Limits, RequestBudget
from jobcu.sources.http import Blocked
from jobcu.sources.matching import matches_places
from jobcu.text import tidy

log = logging.getLogger(__name__)

SITE = "https://www.jobs.ac.uk"
PAGE_SIZE = 25
MAX_PAGES_PER_WORD = 4
LIMITS = Limits(per_search=120)
_DATE = re.compile(r"(\d{1,2})\s+([A-Za-z]{3})")


class JobsAcUkSource(JobSource):
    id = "jobsacuk"
    name = "jobs.ac.uk"
    kind = "job_board"
    # It carries a few jobs elsewhere in Europe, but almost all are in these two countries, so
    # other searches don't spend requests on it.
    countries = frozenset({"GB", "IE"})

    def search(self, query: JobQuery, ctx: SourceContext) -> Iterator[FoundJob]:
        self._budget = RequestBudget(self.id, self.name, LIMITS)
        start = window_start(query.started_at, query.posted_within_hours)
        today = query.started_at.date()
        words = list(dict.fromkeys(t.text for t in query.terms if t.language == "en"))
        seen: set[str] = set()
        try:
            for word in words:
                if ctx.should_stop():
                    return
                for page in range(MAX_PAGES_PER_WORD):
                    jobs = parse_results(self._get(word, page, ctx), today)
                    for job in jobs:
                        if job.source_job_id in seen:
                            continue
                        seen.add(job.source_job_id)
                        countries = countries_in(job.location_text)
                        country = next((c for c in query.countries if c in countries), None)
                        if country is None:
                            continue  # elsewhere, or no place Jobcu can recognise
                        job.country = country
                        if matches_places(query.places, country, job.location_text):
                            yield job
                    # Newest first: when a whole page is older, so is everything after it.
                    if len(jobs) < PAGE_SIZE or all(
                        freshness(j.posted_at, j.date_precision, start) == "too_old" for j in jobs
                    ):
                        break
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
        posting = find_job_posting(response.text)
        if posting is None or not posting.description:
            return job
        return dataclasses.replace(
            job,
            description=posting.description,
            description_is_complete=True,
            company=job.company or posting.company,
            posted_at=posting.date_posted or job.posted_at,
            date_precision="exact" if posting.date_has_time else job.date_precision,
            job_types=job.job_types or posting.job_types,
            work_mode="remote" if posting.remote else job.work_mode,
        )

    def _get(self, word: str, page: int, ctx: SourceContext) -> str:
        self._budget.spend()
        ctx.report.requests += 1
        params = {"keywords": word, "sortOrder": 1, "pageSize": PAGE_SIZE,
                  "startIndex": page * PAGE_SIZE + 1}
        try:
            response = ctx.http.get(f"{SITE}/search/", params=params)
        except httpx.HTTPError as exc:
            raise SourceError("jobs.ac.uk couldn't be reached.") from exc
        if response.status_code == 429:
            raise BudgetExhausted("jobs.ac.uk: asked Jobcu to slow down for now.")
        if response.status_code != 200:
            raise SourceError(f"jobs.ac.uk answered with a problem (code {response.status_code}).")
        return response.text


def placed_on(text: str, today: date) -> date | None:
    """"27 Aug" on the search page, with the year worked out (ads are at most a year old)."""
    match = _DATE.search(text or "")
    if not match:
        return None
    written = f"{match.group(1)} {match.group(2)} {today.year}"
    try:
        day = datetime.strptime(written, "%d %b %Y").date()
    except ValueError:
        return None
    # A date later than today must be from last year.
    return day if day <= today + timedelta(days=1) else day.replace(year=today.year - 1)


def _one_line(text: str) -> str | None:
    """"Salary: £48,822 to £56,535\nGrade 9" → "£48,822 to £56,535 · Grade 9"."""
    cleaned = tidy(text).removeprefix("Salary:").strip()
    return " · ".join(line.strip() for line in cleaned.splitlines() if line.strip()) or None


def parse_results(markup: str, today: date) -> list[FoundJob]:
    try:
        doc = lxml_html.document_fromstring(markup or "<html></html>")
    except (ParserError, ValueError):
        return []
    jobs = []
    for block in doc.xpath("//div[contains(@class, 'j-search-result__result')]"):
        links = block.xpath(".//a[starts-with(@href, '/job/')]")
        if not links:
            continue
        path = links[0].get("href")
        title = tidy(links[0].text_content())
        employer = block.xpath(".//div[contains(@class, 'j-search-result__employer')]")
        location = block.xpath(".//div[starts-with(normalize-space(.), 'Location:')]")
        placed = block.xpath(".//strong[contains(., 'Date Placed')]/..")
        salary = block.xpath(".//div[contains(@class, 'j-search-result__info')]")
        day = placed_on(tidy(placed[0].text_content()) if placed else "", today)
        location_text = tidy(location[0].text_content()).removeprefix("Location:").strip() \
            if location else None
        jobs.append(FoundJob(
            source="jobsacuk",
            source_job_id=block.get("data-advert-id") or path,
            url=f"{SITE}{path}",
            title=title,
            company=tidy(employer[0].text_content()) if employer else None,
            location_text=location_text or None,
            posted_at=day_at_utc(day) if day else None,
            date_precision="day" if day else "unknown",
            salary_text=_one_line(salary[0].text_content()) if salary else None,
        ))
    return jobs
