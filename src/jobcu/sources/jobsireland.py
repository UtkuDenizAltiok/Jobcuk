"""JobsIreland.ie: the Irish public employment service's job board (Department of Social
Protection), checked 2026-09-17.

There's no API. JobsIreland's own browse page loads its job list from a public address that
returns HTML, newest first, with the exact publish time. Its robots.txt allows everything,
and its terms say the information is intended for jobseekers searching for employment
(re-publishing needs permission; Jobcu only shows jobs to the person searching).

The site's keyword search only looks at job titles, so Jobcu reads the newest jobs page by
page until they're older than "Posted within" and matches the titles itself: the same
result as one keyword request per search word, with fewer requests.
"""

import dataclasses
import logging
import re
from collections.abc import Iterator
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import httpx
from lxml import html as lxml_html
from lxml.etree import ParserError

from jobcu.freshness import window_start
from jobcu.sources.base import FoundJob, JobQuery, JobSource, SourceContext, SourceError
from jobcu.sources.budget import BudgetExhausted, Limits, RequestBudget
from jobcu.sources.matching import matches_places, matches_terms
from jobcu.text import tidy

log = logging.getLogger(__name__)

SITE = "https://jobsireland.ie"
LIST_URL = f"{SITE}/Jobsireland.API/JobsIreland/BrowseJobs"
PAGE_SIZE = 100
# About 300 new jobs a day: 40 pages reach back well over a week.
LIMITS = Limits(per_search=60)
MAX_PAGES = 40
IRISH_TIME = ZoneInfo("Europe/Dublin")

# JobsIreland's vacancy types. Community Employment (CE) schemes are part-time placements, and
# Work Placement Experience Programme (WPEP) jobs are work-experience placements.
_VACANCY_TYPES = {
    "0": [],  # paid position: the hours on the job's page tell full or part time
    "3": ["part_time"],
    "4": ["internship_or_working_student"],  # apprenticeship
    "6": ["freelance_or_contract"],  # self-employed
    "10": ["internship_or_working_student"],
}
FULL_TIME_HOURS = 30


class JobsIrelandSource(JobSource):
    id = "jobsireland"
    name = "JobsIreland.ie"
    kind = "job_board"
    countries = frozenset({"IE"})

    def search(self, query: JobQuery, ctx: SourceContext) -> Iterator[FoundJob]:
        self._budget = RequestBudget(self.id, self.name, LIMITS)
        start = window_start(query.started_at, query.posted_within_hours)
        seen: set[str] = set()
        try:
            for page in range(1, MAX_PAGES + 1):
                if ctx.should_stop():
                    return
                jobs = parse_list(self._get(LIST_URL, _list_params(page), ctx))
                for job in jobs:
                    if job.posted_at is not None and job.posted_at < start:
                        return  # newest first: everything after this is older still
                    if job.source_job_id in seen:
                        continue
                    seen.add(job.source_job_id)
                    if matches_terms(query.terms, {"en"}, job.title) and matches_places(
                        query.places, "IE", job.location_text
                    ):
                        yield job
                if len(jobs) < PAGE_SIZE:
                    return
        except BudgetExhausted as exc:
            ctx.report.status = "partial"
            ctx.report.message = exc.message

    def load_details(self, job: FoundJob, ctx: SourceContext) -> FoundJob:
        try:
            page = self._get(job.url, None, ctx)
        except (SourceError, BudgetExhausted):
            return job
        return apply_details(job, page)

    def _get(self, url: str, params: dict | None, ctx: SourceContext) -> str:
        budget = getattr(self, "_budget", None) or RequestBudget(self.id, self.name, LIMITS)
        if params is not None:  # job pages don't count towards the list budget
            budget.spend()
        ctx.report.requests += 1
        try:
            response = ctx.http.get(url, params=params)
        except httpx.HTTPError as exc:
            raise SourceError("JobsIreland.ie couldn't be reached.") from exc
        if response.status_code == 429:
            raise BudgetExhausted("JobsIreland.ie: asked Jobcu to slow down for now.")
        if response.status_code != 200:
            raise SourceError(
                f"JobsIreland.ie answered with a problem (code {response.status_code}). "
                "Its pages may have changed."
            )
        return response.text


def _list_params(page: int) -> dict:
    return {"keyWord": "", "location": "", "page": page, "pageSize": PAGE_SIZE,
            "CareerlevelId": "", "vacancyId": "", "VacancyTypeId": "", "ContractTypeId": ""}


def _document(markup: str):
    try:
        return lxml_html.document_fromstring(markup or "<html></html>")
    except (ParserError, ValueError):
        return lxml_html.document_fromstring("<html></html>")


def _hidden(block, name: str) -> str:
    values = block.xpath(f".//input[@id='{name}']/@value")
    return tidy(values[0]) if values else ""


def _irish_time(text: str) -> datetime | None:
    try:
        local = datetime.fromisoformat(text)
    except ValueError:
        return None
    if local.tzinfo is None:
        local = local.replace(tzinfo=IRISH_TIME)
    return local.astimezone(UTC)


def parse_list(markup: str) -> list[FoundJob]:
    """The jobs on one page of JobsIreland's list, in the site's order (newest first)."""
    doc = _document(markup)
    coordinates: dict[str, tuple[float, float]] = {}
    for item in doc.xpath("//ul[@id='longlats']/li/text()"):
        parts = item.split(";")
        try:
            coordinates.setdefault(parts[-2].strip(), (float(parts[0]), float(parts[1])))
        except (IndexError, ValueError):
            continue
    jobs = []
    for block in doc.xpath("//div[contains(@class, 'job-heading')][@data-vacancyid]"):
        job_id = _hidden(block, "JobId")
        if not job_id.isdigit():
            continue  # the page also carries an empty template
        logo = block.xpath(".//img[starts-with(@alt, 'Logo of ')]/@alt")
        company = tidy(logo[0][len("Logo of "):]) if logo else None
        posted = _irish_time(_hidden(block, "StartDate"))
        latitude, longitude = coordinates.get(job_id, (None, None))
        jobs.append(FoundJob(
            source="jobsireland",
            source_job_id=job_id,
            url=f"{SITE}/en-US/job-Details?id={job_id}",
            title=_hidden(block, "JobTitle"),
            company=company or None,
            location_text=_hidden(block, "Location").strip(" ,") or None,
            country="IE",
            latitude=latitude,
            longitude=longitude,
            posted_at=posted,
            date_precision="exact" if posted else "unknown",
            job_types=list(_VACANCY_TYPES.get(_hidden(block, "VacancyTypeId"), [])),
        ))
    return jobs


def apply_details(job: FoundJob, markup: str) -> FoundJob:
    """Adds the full ad, employer, hours and salary from the job's own page."""
    doc = _document(markup)
    descriptions = doc.xpath("//pre[contains(@ng-bind-html, 'Description')]")
    description = tidy(descriptions[0].text_content()) if descriptions else ""
    if not description:
        return job
    facts: dict[str, str] = {}
    for item in doc.xpath("//ul[contains(@class, 'job-detail_list')]/li"):
        icon = " ".join(item.xpath(".//img/@alt")).lower()
        text = tidy(" ".join(t for t in item.xpath("./div[not(@class)]//text()")))
        if icon and text:
            facts[icon] = text
    company = next((v for k, v in facts.items() if "employer" in k), None)
    hours_text = next((v for k, v in facts.items() if "hours" in k), "")
    salary = next((v for k, v in facts.items() if "euro" in k), None)
    job_types = job.job_types
    hours = re.search(r"(\d+(?:\.\d+)?)\s*hours", hours_text)
    if not job_types and hours:
        full_time = float(hours.group(1)) >= FULL_TIME_HOURS
        job_types = ["full_time_permanent", "fixed_term"] if full_time else ["part_time"]
    return dataclasses.replace(
        job,
        description=description,
        description_is_complete=True,
        company=company or job.company,
        job_types=job_types,
        salary_text=_salary(salary) or job.salary_text,
    )


def _salary(text: str | None) -> str | None:
    """"37000.00 Euro Annually" → "€37,000 a year"; "30000.00 - 34500.00 Euro Annually" →
    "€30,000 – €34,500 a year"."""
    if not text:
        return None
    match = re.match(r"([\d.,]+)(?:\s*-\s*([\d.,]+))?\s*Euro\s*(\w+)?", text)
    if not match:
        return text
    try:
        amounts = [float(a.replace(",", "")) for a in match.group(1, 2) if a]
    except ValueError:
        return text
    amounts = [a for a in amounts if a > 0]
    if not amounts:
        return None
    period = {"annually": " a year", "monthly": " a month", "weekly": " a week",
              "hourly": " an hour", "daily": " a day"}.get((match.group(3) or "").lower(), "")
    return " – ".join(f"€{a:,.2f}".replace(".00", "") for a in dict.fromkeys(amounts)) + period
