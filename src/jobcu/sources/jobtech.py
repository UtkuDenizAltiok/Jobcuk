"""Arbetsförmedlingen (Sweden's public employment service), through its open JobSearch API
(JobTech). Checked 2026-09-21.

`GET https://jobsearch.api.jobtechdev.se/search` returns the ads in Platsbanken, Sweden's
national job board, with their full text. The data is open (CC0) and needs no key. About 1,600
new ads a day.

Jobcu reads every ad published within "Posted within", newest first, and matches the titles,
ad texts and places on its own side. The site's word search treats Swedish compound words as
single words ("kraftelektronik" isn't found by "elektronik"), so reading the whole list finds
more of the right jobs. Only the fields Jobcu uses are asked for, which halves the download.
"""

import math
from collections.abc import Iterator
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import httpx

from jobcu.countries import COUNTRIES
from jobcu.freshness import freshness, window_start
from jobcu.sources.base import FoundJob, JobQuery, JobSource, SourceContext, SourceError
from jobcu.sources.budget import BudgetExhausted, Limits, RequestBudget
from jobcu.sources.matching import matches_places, matches_terms

API = "https://jobsearch.api.jobtechdev.se/search"
PAGE_SIZE = 100
# The API pages only up to the 2,000th ad of one question; older ads are asked for again with
# "published before" set to the oldest ad seen so far.
MAX_OFFSET = 2000
# A week holds about 11,000 ads (110 pages); this leaves room for busy weeks.
LIMITS = Limits(per_search=200)
FIELDS = (
    "total,hits{id,headline,webpage_url,publication_date,removed,employer{name},"
    "workplace_address{city,municipality,region,country,coordinates},employment_type{label},"
    "working_hours_type{label},duration{label},workplace_model{label},salary_description,"
    "application_details{url},description{text}}"
)
SWEDISH_TIME = ZoneInfo("Europe/Stockholm")


class JobTechSource(JobSource):
    id = "jobtech"
    name = "Arbetsförmedlingen (Sweden)"
    kind = "job_board"
    countries = frozenset({"SE"})

    def search(self, query: JobQuery, ctx: SourceContext) -> Iterator[FoundJob]:
        budget = RequestBudget(self.id, self.name, LIMITS)
        start = window_start(query.started_at, query.posted_within_hours)
        # A few minutes more than the window, so no ad is lost to rounding; the exact window is
        # applied to each ad below.
        minutes = math.ceil((datetime.now(UTC) - start).total_seconds() / 60) + 5
        languages = {"en", *COUNTRIES["SE"].ad_languages}
        seen: set[str] = set()
        before: str | None = None
        try:
            while True:
                oldest, count = None, 0
                for offset in range(0, MAX_OFFSET + 1, PAGE_SIZE):
                    if ctx.should_stop():
                        return
                    hits = self._page(minutes, before, offset, budget, ctx)
                    for item in hits:
                        count += 1
                        oldest = item.get("publication_date") or oldest
                        job = to_found_job(item)
                        if job is None or job.source_job_id in seen:
                            continue
                        seen.add(job.source_job_id)
                        if freshness(job.posted_at, job.date_precision, start) == "too_old":
                            continue
                        if not matches_terms(query.terms, languages, job.title, job.description):
                            continue
                        if not matches_places(query.places, "SE", job.location_text):
                            continue
                        yield job
                    if len(hits) < PAGE_SIZE:
                        return
                if oldest is None or oldest == before or count == 0:
                    return
                before = oldest  # the rest of the window is older than this
        except BudgetExhausted as exc:
            ctx.report.status = "partial"
            ctx.report.message = exc.message

    def _page(self, minutes: int, before: str | None, offset: int, budget,
              ctx: SourceContext) -> list[dict]:
        budget.spend()
        ctx.report.requests += 1
        params = {"published-after": minutes, "sort": "pubdate-desc", "limit": PAGE_SIZE,
                  "offset": offset}
        if before:
            params["published-before"] = before
        try:
            # Pages are read once, so they aren't kept in memory for the rest of the search.
            response = ctx.http.get(API, params=params, headers={"X-Fields": FIELDS},
                                    cache=False)
        except httpx.HTTPError as exc:
            raise SourceError("Arbetsförmedlingen couldn't be reached.") from exc
        if response.status_code == 429:
            raise BudgetExhausted("Arbetsförmedlingen: asked Jobcu to slow down for now.")
        if response.status_code != 200:
            raise SourceError(
                f"Arbetsförmedlingen answered with a problem (code {response.status_code})."
            )
        try:
            return response.json().get("hits") or []
        except ValueError as exc:
            raise SourceError("Arbetsförmedlingen didn't answer with a job list.") from exc


def _swedish_time(text: str | None) -> datetime | None:
    try:
        local = datetime.fromisoformat(text or "")
    except ValueError:
        return None
    if local.tzinfo is None:
        local = local.replace(tzinfo=SWEDISH_TIME)
    return local.astimezone(UTC)


def _label(item: dict, name: str) -> str:
    return ((item.get(name) or {}).get("label") or "").lower()


def _job_types(item: dict) -> list[str]:
    """Sweden's employment types, in Jobcu's job types. Unclear ones stay unknown."""
    kind, duration = _label(item, "employment_type"), _label(item, "duration")
    if "tillsvidare" in kind:
        types = ["full_time_permanent"]
    elif any(word in kind for word in ("tidsbegränsad", "säsong", "sommarjobb", "vikariat")):
        types = ["fixed_term"]
    elif "behov" in kind:  # called in when needed
        return ["part_time"]
    elif "vanlig" in kind and duration:  # "regular employment": permanent or for a period
        types = ["full_time_permanent"] if "tills vidare" in duration else ["fixed_term"]
    else:
        types = []
    if "deltid" in _label(item, "working_hours_type"):
        types = [*types, "part_time"] if types else ["part_time"]
    return types


def _work_mode(item: dict) -> str | None:
    model = _label(item, "workplace_model")
    if "distans" in model:
        return "remote"
    if "hybrid" in model:
        return "hybrid"
    return "on_site" if "på plats" in model else None


def _place(address: dict) -> str | None:
    """The town first, then its municipality and county, so both "Kista" and "Stockholm" match.
    Each name once, in its normal spelling ("TÄBY, Täby" is one place)."""
    names: dict[str, str] = {}
    for name in (address.get("city"), address.get("municipality"), address.get("region")):
        name = (name or "").strip()
        if name and (name.lower() not in names or names[name.lower()].isupper()):
            names[name.lower()] = name
    return ", ".join(names.values()) or None


def to_found_job(item: dict) -> FoundJob | None:
    """One ad, or None for ads outside Sweden and ads already taken down."""
    address = item.get("workplace_address") or {}
    if item.get("removed") or (address.get("country") or "Sverige") != "Sverige":
        return None
    posted = _swedish_time(item.get("publication_date"))
    coordinates = address.get("coordinates") or [None, None]
    apply_url = (item.get("application_details") or {}).get("url") or ""
    return FoundJob(
        source="jobtech",
        source_job_id=str(item.get("id") or ""),
        url=item.get("webpage_url") or "",
        title=(item.get("headline") or "").strip(),
        company=(item.get("employer") or {}).get("name") or None,
        location_text=_place(address),
        country="SE",
        # The API gives [longitude, latitude].
        longitude=coordinates[0] if len(coordinates) > 1 else None,
        latitude=coordinates[1] if len(coordinates) > 1 else None,
        posted_at=posted,
        date_precision="exact" if posted else "unknown",
        description=((item.get("description") or {}).get("text") or "").strip(),
        description_is_complete=True,
        job_types=_job_types(item),
        work_mode=_work_mode(item),
        # Mostly the employer's own application system (Varbi, ReachMee, Teamtailor…).
        employer_url=apply_url if apply_url.startswith(("https://", "http://")) else None,
        salary_text=item.get("salary_description") or None,
    )
