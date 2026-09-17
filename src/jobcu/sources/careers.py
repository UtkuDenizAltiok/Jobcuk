"""Company career systems and the employer directory (HANDOVER section 9.3).

Career systems (Greenhouse, Lever, Workday and others) publish each company's job list. They
are usually the original and earliest source of a job, but can't be searched across companies,
so Jobcu ships an **employer directory** (`jobcu/data/employers.json`): employers in the
supported countries and the career system they use. It's general reference data, checked with
`tools/check_employers.py`, never built from anyone's searches.

Each search reads the job lists of the employers that hire in the countries searched, keeps
jobs that are fresh, in those countries and match the search words, and treats the result as
the employer's own ad (the best main link, HANDOVER section 10). One company failing never
stops the others.
"""

import json
import logging
import re
from collections import Counter
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime
from functools import cache
from pathlib import Path

import httpx

from jobcu.countries import COUNTRIES
from jobcu.freshness import freshness, window_start
from jobcu.placenames import OTHER, countries_in, is_europe_wide
from jobcu.sources.base import FoundJob, JobQuery, JobSource, SourceContext, SourceError
from jobcu.sources.budget import BudgetExhausted, Limits, RequestBudget
from jobcu.sources.http import Blocked
from jobcu.sources.matching import matches_places, matches_terms
from jobcu.text import normalise

log = logging.getLogger(__name__)

DIRECTORY = Path(__file__).resolve().parent.parent / "data" / "employers.json"
LIMITS = Limits(per_search=1500)


@dataclass(frozen=True)
class Employer:
    name: str
    system: str
    board: str  # the company's name or address in its career system
    countries: tuple[str, ...]  # supported countries it had jobs in when last checked
    elsewhere: bool = False  # it also hires outside the supported countries


@cache
def load_directory(path: Path = DIRECTORY) -> tuple[Employer, ...]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return tuple(
        Employer(
            name=entry["name"],
            system=entry["system"],
            board=entry["board"],
            countries=tuple(entry.get("countries") or ()),
            elsewhere=bool(entry.get("elsewhere")),
        )
        for entry in data["employers"]
    )


class EmployerNotFound(SourceError):
    """The company's job list doesn't exist (any more) in this career system."""


class CareerSystemSource(JobSource):
    """Common search for one career system. Subclasses read one employer's job list."""

    kind = "employer"
    system: str
    countries = None

    def employers(self, countries: list[str]) -> list[Employer]:
        wanted = set(countries)
        return [e for e in load_directory() if e.system == self.system
                and wanted & set(e.countries)]

    def covers(self, query: JobQuery) -> bool:
        return bool(self.employers(query.countries))

    # Companies read at the same time. Systems where every company has its own server (Workday,
    # Recruitee) can read several at once; the polite pace per server still applies.
    parallel = 1

    def search(self, query: JobQuery, ctx: SourceContext) -> Iterator[FoundJob]:
        self._budget = RequestBudget(self.id, self.name, LIMITS)
        start = window_start(query.started_at, query.posted_within_hours)
        employers = self.employers(query.countries)
        failed: list[str] = []
        stop: list[BaseException] = []  # a problem that ends reading for every company

        def read(employer: Employer) -> list[FoundJob]:
            if stop or ctx.should_stop():
                return []
            try:
                return [kept for job in self.list_jobs(employer, ctx, countries=query.countries,
                                                       start=start)
                        if (kept := keep_job(job, employer, query, start)) is not None]
            except (BudgetExhausted, Blocked) as exc:
                stop.append(exc)
            except SourceError as exc:
                log.info("%s: %s couldn't be read: %s", self.name, employer.name, exc)
                failed.append(employer.name)
            except Exception:  # an unexpected answer from one company never stops the others
                log.exception("%s: reading %s failed", self.name, employer.name)
                failed.append(employer.name)
            return []

        with ThreadPoolExecutor(max_workers=self.parallel, thread_name_prefix=self.id) as pool:
            for jobs in pool.map(read, employers):
                yield from jobs
        if stop and isinstance(stop[0], Blocked):
            raise stop[0]
        if stop:
            ctx.report.status = "partial"
            ctx.report.message = f"{stop[0].message} Some companies weren't read."
            return
        if failed and len(failed) == len(employers):
            raise SourceError(f"None of the {len(employers)} companies' job lists could be read.")
        if failed:
            ctx.report.status = "partial"
            ctx.report.message = (
                f"{self.name}: {len(failed)} of {len(employers)} companies' job lists couldn't "
                f"be read ({', '.join(failed[:5])}{'…' if len(failed) > 5 else ''})."
            )

    def list_jobs(
        self,
        employer: Employer,
        ctx: SourceContext,
        *,
        countries: list[str] | None = None,
        start: datetime | None = None,
    ) -> Iterator[FoundJob]:
        """The employer's jobs. `countries` and `start` are hints a system may use to read less;
        without them, every job is listed (used by the directory check)."""
        raise NotImplementedError

    def country_counts(self, employer: Employer, ctx: SourceContext) -> Counter:
        """How many jobs the employer has per supported country (and OTHER), for the directory
        check."""
        counts: Counter = Counter()
        for job in self.list_jobs(employer, ctx):
            for code in job_countries(job) or {"unknown"}:
                counts[code] += 1
        return counts

    def get(self, url: str, ctx: SourceContext, **kwargs) -> httpx.Response:
        """One request, counted and checked. 404 means the company's list doesn't exist."""
        budget = getattr(self, "_budget", None)
        if budget is not None:
            budget.spend()
        ctx.report.requests += 1
        method = kwargs.pop("method", "GET")
        try:
            response = ctx.http.request(method, url, **kwargs)
        except httpx.HTTPError as exc:
            raise SourceError(f"{self.name} couldn't be reached.") from exc
        if response.status_code in (404, 410):
            raise EmployerNotFound(f"No job list at {self.name} (code {response.status_code}).")
        if response.status_code == 429:
            raise BudgetExhausted(f"{self.name}: asked Jobcu to slow down for now.")
        if response.status_code != 200:
            raise SourceError(f"{self.name} answered with a problem (code {response.status_code}).")
        return response

    def get_json(self, url: str, ctx: SourceContext, **kwargs):
        response = self.get(url, ctx, **kwargs)
        try:
            return response.json()
        except ValueError as exc:
            raise SourceError(f"{self.name} didn't answer with a job list.") from exc


def job_countries(job: FoundJob) -> set[str]:
    """Supported country codes the job is in, OTHER for places elsewhere, empty if unclear."""
    if job.country:
        return {job.country if job.country in COUNTRIES else OTHER}
    return countries_in(job.location_text)


def keep_job(job: FoundJob, employer: Employer, query: JobQuery, start: datetime):
    """The job with its country filled in, or None if it's too old, elsewhere or unrelated."""
    if freshness(job.posted_at, job.date_precision, start) == "too_old":
        return None
    searched = list(query.countries)
    found = job_countries(job)
    in_searched = [code for code in searched if code in found]
    if in_searched:
        country = in_searched[0]
    elif found - {OTHER}:
        return None  # in a supported country that wasn't searched
    elif OTHER in found and not is_europe_wide(job.location_text):
        return None
    elif employer.elsewhere and not is_europe_wide(job.location_text):
        return None  # location unclear, and the company also hires far away
    elif not set(employer.countries) & set(searched):
        return None
    else:
        matching = [code for code in searched if code in employer.countries]
        country = matching[0] if len(matching) == 1 else None
    languages = {"en"}
    for code in [country] if country else searched:
        languages.update(COUNTRIES[code].ad_languages)
    if not matches_terms(query.terms, languages, job.title, job.description):
        return None
    if country and not matches_places(query.places, country, job.location_text):
        return None
    job.country = country
    job.company = job.company or employer.name
    job.employer_url = job.employer_url or job.url
    return job


_JOB_TYPE_WORDS = [
    (re.compile(r"\b(intern|internship|praktik\w*|werkstudent\w*|working student|trainee|"
                r"apprentice\w*|ausbildung|graduate programme|co op|stage|stagiaire)\b"),
     "internship_or_working_student"),
    (re.compile(r"\b(part time|parttime|teilzeit|temps partiel)\b"), "part_time"),
    (re.compile(r"\b(contract|contractor|freelance\w*|freiberuf\w*)\b"), "freelance_or_contract"),
    (re.compile(r"\b(fixed term|fixedterm|temporary|temp|befristet|maternity cover|cdd)\b"),
     "fixed_term"),
    (re.compile(r"\b(permanent|unbefristet|regular|cdi)\b"), "full_time_permanent"),
]


def job_types_from_text(text: str | None) -> list[str]:
    """Job types from a career system's wording ("Full-time", "Permanent", "Intern")."""
    words = normalise(text).replace("_", " ")
    if not words:
        return []
    types = [kind for pattern, kind in _JOB_TYPE_WORDS if pattern.search(words)]
    part_time = ["part_time"] if "part_time" in types else []
    if "internship_or_working_student" in types:
        return ["internship_or_working_student", *part_time]
    if "freelance_or_contract" in types:
        # A "contract" role is often a fixed-term employment contract, so both are kept.
        return ["freelance_or_contract", "fixed_term", *part_time]
    if part_time and "full time" not in words:
        return ["part_time"]
    if not types and re.search(r"\b(full time|fulltime|vollzeit|temps plein)\b", words):
        return ["full_time_permanent", "fixed_term"]
    return types


def work_mode_from_text(text: str | None) -> str | None:
    words = normalise(text)
    if re.search(r"\bhybrid\b", words):
        return "hybrid"
    if re.search(r"\b(remote|fully remote|home office|homeoffice)\b", words):
        return "remote"
    if re.search(r"\b(on site|onsite|in office|office)\b", words):
        return "on_site"
    return None
