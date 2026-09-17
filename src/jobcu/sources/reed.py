"""Reed: an official UK job search API with a free key.

Reed can't combine search words and returns results in no date order, so each search
word is its own request, pages are read through, and only fresh jobs get a second
request for the full ad. Reed gives posting dates by day.
"""

import logging
from collections.abc import Iterator
from datetime import datetime

import httpx

from jobcu.freshness import day_at_utc, freshness, window_start
from jobcu.keystore import KeyStore
from jobcu.sources.base import FoundJob, JobQuery, JobSource, SourceContext, SourceError
from jobcu.sources.budget import BudgetExhausted, Limits, RequestBudget
from jobcu.sources.http import KeyCheck, client
from jobcu.text import html_to_text

log = logging.getLogger(__name__)

API = "https://www.reed.co.uk/api/1.0"
KEY_API_KEY = "reed_api_key"
PAGE_SIZE = 100
MAX_PAGES_PER_WORD = 5
DEFAULT_RADIUS_MILES = 15
LIMITS = Limits(per_search=400)


class ReedSource(JobSource):
    id = "reed"
    name = "Reed"
    kind = "job_board"
    countries = frozenset({"GB"})

    def unavailable_reason(self, keys: KeyStore) -> str | None:
        return None if keys.get(KEY_API_KEY) else "Reed: no key saved in Settings."

    def search(self, query: JobQuery, ctx: SourceContext) -> Iterator[FoundJob]:
        auth = (ctx.keys.get(KEY_API_KEY), "")
        self._budget = RequestBudget(self.id, self.name, LIMITS)
        start = window_start(query.started_at, query.posted_within_hours)
        places = [p for p in query.places if p.country == "GB"] or [None]
        words = list(dict.fromkeys(t.text for t in query.terms if t.language == "en"))
        seen: set[int] = set()
        try:
            for place in places:
                for word in words:
                    if ctx.should_stop():
                        return
                    for item in self._search_word(word, place, auth, self._budget, ctx):
                        posted = _parse_day(item.get("date"))
                        if freshness(posted, "day" if posted else "unknown", start) == "too_old":
                            continue
                        if item["jobId"] not in seen:
                            seen.add(item["jobId"])
                            yield to_found_job(item)
        except BudgetExhausted as exc:
            ctx.report.status = "partial"
            ctx.report.message = exc.message

    def load_details(self, job: FoundJob, ctx: SourceContext) -> FoundJob:
        budget = getattr(self, "_budget", None) or RequestBudget(self.id, self.name, LIMITS)
        try:
            details = self._get(
                f"{API}/jobs/{job.source_job_id}", {}, (ctx.keys.get(KEY_API_KEY), ""), budget, ctx
            )
        except (SourceError, BudgetExhausted):
            return job
        item = {"jobId": job.source_job_id, "jobUrl": job.url, "jobTitle": job.title,
                "employerName": job.company, "locationName": job.location_text}
        return to_found_job(item, details)

    def _search_word(self, word, place, auth, budget, ctx) -> Iterator[dict]:
        skip = 0
        for _ in range(MAX_PAGES_PER_WORD):
            params = {"keywords": word, "resultsToTake": PAGE_SIZE, "resultsToSkip": skip}
            if place is not None:
                params["locationName"] = place.name
                miles = (place.radius_km or DEFAULT_RADIUS_MILES * 1.609) / 1.609
                params["distanceFromLocation"] = round(miles)
            data = self._get(f"{API}/search", params, auth, budget, ctx)
            results = data.get("results") or []
            yield from results
            skip += PAGE_SIZE
            if len(results) < PAGE_SIZE or skip >= (data.get("totalResults") or 0):
                return

    def _get(self, url, params, auth, budget, ctx) -> dict:
        budget.spend()
        ctx.report.requests += 1
        try:
            response = ctx.http.get(url, params=params, auth=auth)
        except httpx.HTTPError as exc:
            raise SourceError("Reed couldn't be reached.") from exc
        if response.status_code in (401, 403):
            raise SourceError("Reed didn't accept the key. Check it in Settings.")
        if response.status_code == 429:
            raise BudgetExhausted("Reed: its usage limit is reached for now.")
        if response.status_code != 200:
            raise SourceError(f"Reed answered with a problem (code {response.status_code}).")
        return response.json()


def _parse_day(text: str | None) -> datetime | None:
    try:
        return day_at_utc(datetime.strptime(text or "", "%d/%m/%Y").date())
    except ValueError:
        return None


def _job_types(details: dict) -> list[str]:
    contract = (details.get("contractType") or "").lower()
    part_time, full_time = details.get("partTime"), details.get("fullTime")
    if contract == "permanent":
        if part_time and not full_time:
            return ["part_time"]
        return ["full_time_permanent"] if full_time else ["full_time_permanent", "part_time"]
    if contract == "temporary":
        return ["fixed_term", "part_time"] if part_time else ["fixed_term"]
    if contract == "contract":
        return ["freelance_or_contract", "fixed_term"]
    return []


def to_found_job(item: dict, details: dict | None = None) -> FoundJob:
    source = details or item
    posted = _parse_day(source.get("datePosted") or item.get("date"))
    low, high = source.get("minimumSalary"), source.get("maximumSalary")
    salary = None
    if low:
        salary = f"£{low:,.0f}" + (f" – £{high:,.0f}" if high and high != low else "")
    external = (details or {}).get("externalUrl") or None
    return FoundJob(
        source="reed",
        source_job_id=str(item.get("jobId")),
        url=item.get("jobUrl") or f"https://www.reed.co.uk/jobs/{item.get('jobId')}",
        title=(item.get("jobTitle") or "").strip(),
        company=item.get("employerName") or None,
        location_text=item.get("locationName"),
        country="GB",
        posted_at=posted,
        date_precision="day" if posted else "unknown",
        description=html_to_text(source.get("jobDescription")),
        description_is_complete=details is not None,
        job_types=_job_types(details) if details else [],
        employer_url=external,
        salary_text=salary,
    )


def check_keys(keys: KeyStore) -> KeyCheck:
    api_key = keys.get(KEY_API_KEY)
    if not api_key:
        return KeyCheck(False, "Please save the Reed key first.")
    try:
        with client() as http:
            # Reed expects the key as the user name, with an empty password.
            response = http.get(
                f"{API}/search", params={"keywords": "engineer", "resultsToTake": 1},
                auth=(api_key, ""),
            )
    except httpx.HTTPError as exc:
        log.warning("Reed key check failed: %s", type(exc).__name__)
        return KeyCheck(False, "Jobcu couldn't reach Reed. Check your internet connection.")
    if response.status_code == 200:
        return KeyCheck(True, "Reed key works.")
    if response.status_code in (401, 403):
        return KeyCheck(False, "Reed didn't accept this key. Check that you copied the whole key.")
    if response.status_code == 429:
        return KeyCheck(False, "Reed says its usage limit is reached. Try again later.")
    return KeyCheck(
        False, f"Reed answered with an unexpected problem (code {response.status_code})."
    )
