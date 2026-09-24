"""NHS Jobs: jobs in the NHS in England and Wales, and in GP practices, hospices and health
charities (NHS Business Services Authority), checked 2026-09-24.

An open XML search feed lists the live jobs (about 12,700) newest first, with the exact time
each was posted, the employer, the contract and the salary: roughly 1,000 new a day. Jobcu
reads the window page by page (100 jobs a page) and matches titles and places on its own side.
The site has no robots.txt, and its terms are about accounts and applications.

The feed's text is a short opening; the job's page has the whole ad, including the person
specification (the essential qualifications and registrations), so it is read for the jobs
still in the running.
"""

import dataclasses
import re
import xml.etree.ElementTree as ElementTree
from collections.abc import Iterator
from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

import httpx
from lxml import html as lxml_html
from lxml.etree import ParserError

from jobcu.freshness import end_of_day, freshness, window_start
from jobcu.sources.base import FoundJob, JobQuery, JobSource, SourceContext, SourceError
from jobcu.sources.budget import BudgetExhausted, Limits, RequestBudget
from jobcu.sources.http import Blocked
from jobcu.sources.matching import matches_places, matches_terms
from jobcu.text import html_to_text, tidy

SITE = "https://www.jobs.nhs.uk"
FEED = f"{SITE}/api/v1/search_xml"
PAGE_SIZE = 100
# About 1,000 new jobs a day: 40 pages reach back about four days.
LIMITS = Limits(per_search=40)
UK_TIME = ZoneInfo("Europe/London")

# The feed's contract types. "Bank" staff are called in when needed, like Sweden's
# "behovsanställning"; "Permanent" says nothing about the hours, which the job's page gives.
_CONTRACTS = {
    "fixed-term": ["fixed_term"],
    "fixed term": ["fixed_term"],
    "secondment": ["fixed_term"],
    "locum": ["fixed_term"],
    "bank": ["part_time"],
    "apprenticeship": ["internship_or_working_student"],
    "training": ["internship_or_working_student"],
}


class NhsJobsSource(JobSource):
    id = "nhsjobs"
    name = "NHS Jobs (England and Wales)"
    kind = "job_board"
    countries = frozenset({"GB"})

    def search(self, query: JobQuery, ctx: SourceContext) -> Iterator[FoundJob]:
        budget = RequestBudget(self.id, self.name, LIMITS)
        start = window_start(query.started_at, query.posted_within_hours)
        page = 1
        try:
            while not ctx.should_stop():
                jobs, last_page = self._page(page, budget, ctx)
                for job in jobs:
                    if freshness(job.posted_at, job.date_precision, start) == "too_old":
                        continue
                    if not matches_terms(query.terms, {"en", "cy"}, job.title, job.description):
                        continue
                    if matches_places(query.places, "GB", job.location_text):
                        yield job
                # Newest first: once a job is older than the window, every later page is too.
                if page >= last_page or len(jobs) < PAGE_SIZE or any(
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
        return apply_details(job, response.text)

    def _page(self, page: int, budget: RequestBudget,
              ctx: SourceContext) -> tuple[list[FoundJob], int]:
        budget.spend()
        ctx.report.requests += 1
        params = {"sort": "publicationDateDesc", "limit": PAGE_SIZE, "page": page}
        try:
            response = ctx.http.get(FEED, params=params, cache=False)
        except httpx.HTTPError as exc:
            raise SourceError("NHS Jobs couldn't be reached.") from exc
        if response.status_code == 429:
            raise BudgetExhausted("NHS Jobs: asked Jobcu to slow down for now.")
        if response.status_code != 200:
            raise SourceError(f"NHS Jobs answered with a problem (code {response.status_code}).")
        return parse_feed(response.text)


def parse_feed(xml: str) -> tuple[list[FoundJob], int]:
    try:
        root = ElementTree.fromstring(xml)
    except ElementTree.ParseError:
        raise SourceError("NHS Jobs didn't answer with its job list.") from None
    jobs = [job for job in map(to_found_job, root.iter("vacancyDetails")) if job]
    try:
        last_page = int(root.findtext("totalPages") or 1)
    except ValueError:
        last_page = 1
    return jobs, last_page


def _uk_time(text: str) -> datetime | None:
    """ "2026-09-24T12:18:24.800841778": UK time without a zone, with nanoseconds."""
    found = re.match(r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(\.\d{1,6})?", text or "")
    if not found:
        return None
    local = datetime.fromisoformat(found.group(1) + (found.group(2) or ""))
    return local.replace(tzinfo=UK_TIME).astimezone(UTC)


def _salary(text: str) -> str | None:
    """ "£49387.00 to £56515.00" → "£49,387 to £56,515"."""
    def pounds(found: re.Match) -> str:
        return f"£{float(found.group(1)):,.0f}"
    text = tidy(text or "")
    return re.sub(r"£(\d+(?:\.\d+)?)", pounds, text) or None


def _text(element, name: str) -> str:
    return tidy(element.findtext(name) or "")


def to_found_job(vacancy) -> FoundJob | None:
    reference, title = _text(vacancy, "reference"), _text(vacancy, "title")
    if not reference or not title:
        return None
    places = [tidy(place.text or "") for place in vacancy.iter("location") if place.text]
    posted = _uk_time(_text(vacancy, "postDate"))
    try:
        closing = end_of_day(date.fromisoformat(_text(vacancy, "closeDate")[:10]), UK_TIME)
    except ValueError:
        closing = None
    return FoundJob(
        source="nhsjobs",
        source_job_id=reference,
        # The feed links to beta.jobs.nhs.uk; the same page lives on the main address.
        url=f"{SITE}/candidate/jobadvert/{reference}",
        title=title,
        company=_text(vacancy, "employer") or None,
        location_text="; ".join(dict.fromkeys(places)) or None,
        country="GB",
        posted_at=posted,
        date_precision="exact" if posted else "unknown",
        description=_text(vacancy, "description"),
        job_types=_CONTRACTS.get(_text(vacancy, "type").lower(), []),
        salary_text=_salary(_text(vacancy, "salary")),
        closes_at=closing,
    )


def _first_text(document, path: str) -> str:
    found = document.xpath(path)
    return tidy(found[0].text_content()) if found else ""


def _job_types(contract: str, pattern: str, known: list[str]) -> list[str]:
    contract, pattern = contract.lower(), pattern.lower()
    types = list(_CONTRACTS.get(contract, []))
    if contract == "permanent" and "full-time" in pattern:
        types.append("full_time_permanent")
    if "part-time" in pattern and "part_time" not in types:
        types.append("part_time")
    return types or known


def apply_details(job: FoundJob, page: str) -> FoundJob:
    """The whole ad from the job's page. A page without one keeps the summary."""
    try:
        document = lxml_html.document_fromstring(page or "<html></html>")
    except (ParserError, ValueError):
        return job
    main = document.xpath("//main")
    if not main:
        return job
    contract = _first_text(document, "//p[@id='contract_type']")
    pattern = _first_text(document, "//h3[@id='working_pattern_heading']/following-sibling::p[1]")
    # The page repeats its details for small screens.
    for copy in main[0].xpath(".//*[contains(@class, 'show-mobile')]|.//form|.//nav"):
        copy.drop_tree()
    text = html_to_text(lxml_html.tostring(main[0], encoding="unicode"))
    if len(text) <= len(job.description):
        return job
    return dataclasses.replace(
        job,
        description=text,
        description_is_complete=True,
        job_types=_job_types(contract, pattern, job.job_types),
    )
