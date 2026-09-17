"""EURAXESS: research jobs at universities, institutes and research-heavy companies all over
Europe (the European Commission's researcher portal). Checked 2026-09-17.

There's no API, but the search page is plain HTML and can be sorted newest first
(`sort[name]=created&sort[direction]=DESC`). Each result gives the country, the organisation,
the day it was posted and a first paragraph; the job's own page has the whole ad.

robots.txt allows `/jobs/search`, and the Commission's legal notice allows reuse of its content
with the source named; no rule against automated reading was found (unlike EURES, whose terms
allow it only for EURES partner organisations). Jobcu still asks politely: 2 seconds between
requests, and it stops as soon as the jobs are older than "Posted within".
"""

import dataclasses
import logging
import re
from collections.abc import Iterator
from datetime import date, datetime

import httpx
import trafilatura
from lxml import html as lxml_html
from lxml.etree import ParserError

from jobcu.freshness import day_at_utc, freshness, window_start
from jobcu.placenames import countries_in
from jobcu.sources.base import FoundJob, JobQuery, JobSource, SourceContext, SourceError
from jobcu.sources.budget import BudgetExhausted, Limits, RequestBudget
from jobcu.sources.careers import job_types_from_text
from jobcu.sources.http import Blocked
from jobcu.sources.matching import matches_places
from jobcu.text import tidy

log = logging.getLogger(__name__)

SITE = "https://euraxess.ec.europa.eu"
RESULTS_PER_PAGE = 10
MAX_PAGES_PER_WORD = 3
LIMITS = Limits(per_search=80)
_POSTED = re.compile(r"Posted on:\s*(\d{1,2}\s+\w+\s+\d{4})")


class EuraxessSource(JobSource):
    id = "euraxess"
    name = "EURAXESS (research jobs)"
    kind = "job_board"

    def search(self, query: JobQuery, ctx: SourceContext) -> Iterator[FoundJob]:
        self._budget = RequestBudget(self.id, self.name, LIMITS)
        start = window_start(query.started_at, query.posted_within_hours)
        words = list(dict.fromkeys(t.text for t in query.terms if t.language == "en"))
        seen: set[str] = set()
        try:
            for word in words:
                if ctx.should_stop():
                    return
                for page in range(MAX_PAGES_PER_WORD):
                    jobs = parse_results(self._get(word, page, ctx))
                    for job in jobs:
                        if job.source_job_id in seen:
                            continue
                        seen.add(job.source_job_id)
                        if job.country not in query.countries:
                            continue
                        if freshness(job.posted_at, job.date_precision, start) == "too_old":
                            continue
                        if matches_places(query.places, job.country, job.location_text):
                            yield job
                    # Newest first: a page with nothing fresh means the rest is older.
                    if len(jobs) < RESULTS_PER_PAGE or all(
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
        text = trafilatura.extract(response.text, include_comments=False, include_tables=True,
                                   favor_recall=True) or ""
        text = tidy(text)
        if len(text) <= len(job.description):
            return job
        return dataclasses.replace(
            job,
            description=text,
            description_is_complete=True,
            job_types=job.job_types or _job_types(text),
        )

    def _get(self, word: str, page: int, ctx: SourceContext) -> str:
        self._budget.spend()
        ctx.report.requests += 1
        params = {"keywords": word, "sort[name]": "created", "sort[direction]": "DESC",
                  "page": page}
        try:
            response = ctx.http.get(f"{SITE}/jobs/search", params=params)
        except httpx.HTTPError as exc:
            raise SourceError("EURAXESS couldn't be reached.") from exc
        if response.status_code == 429:
            raise BudgetExhausted("EURAXESS: asked Jobcu to slow down for now.")
        if response.status_code != 200:
            raise SourceError(f"EURAXESS answered with a problem (code {response.status_code}).")
        return response.text


def _job_types(text: str) -> list[str]:
    """EURAXESS job pages list "Type of Contract" and "Job Status" as plain lines."""
    parts = []
    for label in ("Type of Contract", "Job Status"):
        match = re.search(rf"{label}\s*[\n:-]+\s*([^\n]+)", text)
        if match:
            parts.append(match.group(1))
    return job_types_from_text(" ".join(parts))


def posted_on(text: str) -> date | None:
    match = _POSTED.search(text or "")
    if not match:
        return None
    try:
        return datetime.strptime(match.group(1), "%d %B %Y").date()
    except ValueError:
        return None


def _place(text: str) -> str | None:
    """"Work Locations: Number of offers: 1, Spain, …, Madrid, 28046" → the address part."""
    cleaned = re.sub(r"\s+", " ", tidy(text))
    cleaned = re.sub(r"^\s*Work Locations:\s*", "", cleaned)
    cleaned = re.sub(r"Number of offers:\s*\d+,?\s*", "", cleaned)
    return cleaned.strip(" ,")[:200] or None


def parse_results(markup: str) -> list[FoundJob]:
    try:
        doc = lxml_html.document_fromstring(markup or "<html></html>")
    except (ParserError, ValueError):
        return []
    jobs = []
    for block in doc.xpath("//div[@id='job-teaser-content']"):
        links = block.xpath(".//h3[contains(@class, 'ecl-content-block__title')]//a[@href]")
        if not links:
            continue
        path = links[0].get("href")
        labels = [tidy(node.text_content())
                  for node in block.xpath(".//span[contains(@class, 'ecl-label')]")]
        countries = {code for label in labels for code in countries_in(label)}
        country = next(iter(countries)) if len(countries) == 1 else None
        meta = " ".join(tidy(node.text_content()) for node in block.xpath(
            ".//li[contains(@class, 'ecl-content-block__primary-meta-item')]"))
        organisations = block.xpath(
            ".//li[contains(@class, 'ecl-content-block__primary-meta-item')]//a")
        summary = block.xpath(".//div[contains(@class, 'ecl-content-block__description')]")
        locations = block.xpath(".//div[contains(@class, 'id-Work-Locations')]")
        day = posted_on(meta)
        jobs.append(FoundJob(
            source="euraxess",
            source_job_id=path.rstrip("/").rsplit("/", 1)[-1],
            url=f"{SITE}{path}" if path.startswith("/") else path,
            title=tidy(links[0].text_content()),
            company=tidy(organisations[0].text_content()) if organisations else None,
            location_text=_place(locations[0].text_content()) if locations else (
                labels[-1] if labels else None),
            country=country,
            posted_at=day_at_utc(day) if day else None,
            date_precision="day" if day else "unknown",
            description=tidy(summary[0].text_content()) if summary else "",
        ))
    return jobs
