"""Workday career sites (used by many large employers). Checked 2026-09-17.

Workday has no documented public API. Each company's career site (e.g.
`https://analogdevices.wd1.myworkdayjobs.com/External`) loads its jobs from
`POST /wday/cxs/{tenant}/{site}/jobs` with `{"appliedFacets": {}, "limit": 20, "offset": 0,
"searchText": ""}`. The answer lists 20 jobs at a time, newest first, with the title, place
text and a relative date ("Posted Today", "Posted 3 Days Ago", "Posted 30+ Days Ago"), plus
filters such as the job's country with an ID each. A job's full ad and exact day come from
`GET /wday/cxs/{tenant}/{site}{externalPath}`.

Because the address isn't documented, Jobcu checks each site's robots.txt first and skips the
company if it disallows these addresses.
"""

import dataclasses
import re
from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta
from urllib.parse import urlsplit

from jobcu import places as place_list
from jobcu.freshness import day_at_utc, freshness
from jobcu.placenames import OTHER, countries_in
from jobcu.sources.base import FoundJob, SourceContext, SourceError
from jobcu.sources.budget import BudgetExhausted
from jobcu.sources.careers import (
    CareerSystemSource,
    Employer,
    Survey,
    job_types_from_text,
    work_mode_from_text,
)
from jobcu.text import html_to_text

PAGE_SIZE = 20
MAX_PAGES_PER_COUNTRY = 25
HEADERS = {"Accept": "application/json", "Accept-Language": "en-US"}
_POSTED = re.compile(r"posted\s+(today|yesterday|(\d+)\+?\s+days?\s+ago)", re.IGNORECASE)


@dataclasses.dataclass(frozen=True)
class Site:
    host: str
    tenant: str
    site: str

    @property
    def api(self) -> str:
        return f"https://{self.host}/wday/cxs/{self.tenant}/{self.site}"


def parse_board(board: str) -> Site:
    """"https://acme.wd3.myworkdayjobs.com/en-US/Careers" → host, tenant "acme", site
    "Careers"."""
    parts = urlsplit(board if "//" in board else f"https://{board}")
    host = parts.hostname or ""
    segments = [s for s in parts.path.split("/") if s and not re.fullmatch(r"[a-z]{2}-[A-Z]{2}", s)]
    if not host or not segments:
        raise SourceError(f"Not a Workday career site address: {board}")
    return Site(host=host, tenant=host.split(".")[0], site=segments[0])


def posted_day(text: str | None, today: date) -> date | None:
    match = _POSTED.search(text or "")
    if not match:
        return None
    word = match.group(1).lower()
    if word == "today":
        return today
    if word == "yesterday":
        return today - timedelta(days=1)
    return today - timedelta(days=int(match.group(2)))


class WorkdaySource(CareerSystemSource):
    id = "workday"
    name = "Company career sites (Workday)"
    system = "workday"
    parallel = 4

    def list_jobs(self, employer: Employer, ctx: SourceContext, *, countries=None, start=None,
                  terms=None) -> Iterator[FoundJob]:
        site = parse_board(employer.board)
        self._check_robots(site, ctx)
        today = datetime.now(UTC).date()
        first = self._page(site, {}, 0, ctx)
        facets = country_facets(first)
        parameter = _country_facet(first.get("facets"))[0]
        wanted: list[tuple[str | None, list[str]]] = [(None, [])]
        if countries is not None and facets:
            wanted = [(code, [facet_id for facet_id, codes in facets.items() if code in codes])
                      for code in countries]
            wanted = [(code, ids) for code, ids in wanted if ids]
        for code, ids in wanted:
            for page in range(MAX_PAGES_PER_COUNTRY):
                data = first if not ids and page == 0 else self._page(
                    site, {parameter: ids} if ids else {}, page * PAGE_SIZE, ctx)
                postings = data.get("jobPostings") or []
                too_old = 0
                for item in postings:
                    job = to_found_job(item, site, employer, code, today)
                    if start and freshness(job.posted_at, job.date_precision, start) == "too_old":
                        too_old += 1
                    yield job
                # Lists come newest first; a page of only older jobs means the rest is older.
                if len(postings) < PAGE_SIZE or (start and too_old == len(postings)):
                    break

    def survey(self, employer: Employer, ctx: SourceContext) -> Survey:
        """Workday's own filters already say how many jobs are in each country and town."""
        site = parse_board(employer.board)
        self._check_robots(site, ctx)
        answer = self._page(site, {}, 0, ctx)
        values = _country_facet(answer.get("facets"))[1]
        if not values:  # a site without a country filter: look at the jobs themselves
            return super().survey(employer, ctx)
        survey = Survey()
        for value in values:
            codes = {c for c in countries_in(value.get("descriptor")) if c != OTHER}
            for code in codes or {OTHER}:
                survey.counts[code] += int(value.get("count") or 0)
        for name, entries in _all_facets(answer.get("facets")):
            if "location" not in name.lower():
                continue
            for value in entries:  # "Germany, Munich" and the like
                for code in countries_in(value.get("descriptor")) - {OTHER}:
                    town = place_list.locate(value.get("descriptor"), code)
                    if town is not None:
                        survey.towns.setdefault(code, set()).add(town.name)
        return survey

    def load_details(self, job: FoundJob, ctx: SourceContext) -> FoundJob:
        try:
            info = self.get_json(job.source_job_id, ctx, headers=HEADERS).get(
                "jobPostingInfo") or {}
        except (SourceError, BudgetExhausted, ValueError):
            return job
        description = html_to_text(info.get("jobDescription"))
        if not description:
            return job
        try:
            posted = day_at_utc(date.fromisoformat(info.get("startDate") or ""))
        except ValueError:
            posted = job.posted_at
        return dataclasses.replace(
            job,
            description=description,
            description_is_complete=True,
            posted_at=posted,
            job_types=job_types_from_text(info.get("timeType")) or job.job_types,
            work_mode=work_mode_from_text(info.get("remoteType")) or job.work_mode,
        )

    def _page(self, site: Site, facets: dict, offset: int, ctx: SourceContext) -> dict:
        body = {"appliedFacets": facets, "limit": PAGE_SIZE, "offset": offset, "searchText": ""}
        return self.get_json(f"{site.api}/jobs", ctx, method="POST", json=body, headers=HEADERS)

    def _check_robots(self, site: Site, ctx: SourceContext) -> None:
        if not self.allowed(f"{site.api}/jobs", ctx):
            raise SourceError(f"{site.host} asks automated tools not to read its job list.")


def _all_facets(facets: list) -> Iterator[tuple[str, list[dict]]]:
    for facet in facets or []:
        values = facet.get("values") or []
        if values and isinstance(values[0], dict) and "facetParameter" in values[0]:
            yield from _all_facets(values)
        elif values:
            yield facet.get("facetParameter") or "", values


def _country_facet(facets: list) -> tuple[str, list[dict]]:
    """The site's filter that stands for countries, and its values.

    Career sites name it differently ("locationCountry", "locationHierarchy1" with country
    names, or "locations" with "Ireland, Limerick"), so Jobcu picks the location filter whose
    entries name a country most clearly, preferring the one with the fewest entries (the
    country level rather than every office).
    """
    best: tuple[float, int, str, list[dict]] | None = None
    for parameter, values in _all_facets(facets):
        if "location" not in parameter.lower() and "country" not in parameter.lower():
            continue
        named = sum(1 for value in values if len(countries_in(value.get("descriptor"))) == 1)
        share = named / len(values)
        if share < 0.6:
            continue
        rank = (-share, len(values), 0 if "country" in parameter.lower() else 1)
        if best is None or rank < best[0]:
            best = (rank, parameter, values)
    if best is None:
        return "", []
    return best[1], best[2]


def country_facets(data: dict) -> dict[str, set[str]]:
    """The country filter's IDs and the supported countries they stand for."""
    return {value["id"]: {c for c in countries_in(value.get("descriptor")) if c != OTHER}
            for value in _country_facet(data.get("facets"))[1] if value.get("id")}


def to_found_job(item: dict, site: Site, employer: Employer, country: str | None,
                 today: date) -> FoundJob:
    path = item.get("externalPath") or ""
    day = posted_day(item.get("postedOn"), today)
    location = item.get("locationsText")
    if location and re.fullmatch(r"\d+ Locations?", location):
        location = None  # "5 Locations": the country filter tells the country
    return FoundJob(
        source="workday",
        source_job_id=f"{site.api}{path}",
        url=f"https://{site.host}/{site.site}{path}",
        title=(item.get("title") or "").strip(),
        company=employer.name,
        location_text=location,
        country=country,
        posted_at=day_at_utc(day) if day else None,
        date_precision="day" if day else "unknown",
        work_mode=work_mode_from_text(location),
    )
