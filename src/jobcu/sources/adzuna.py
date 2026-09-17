"""Adzuna: an official job search API with a free key (Application ID + Application Key).

Free keys allow 25 requests a minute, 250 a day and 2,500 a month, so Adzuna is
queried economically:
- single-word search words (e.g. "Leistungselektronik") are combined into one request,
  because Adzuna can search for "any of these words";
- multi-word phrases ("power electronics") need a request each, so field words come
  first, then job titles, until this search's share of requests is used;
- results come newest first, so paging stops as soon as jobs are older than the window.

The API gives only the start of each ad. With the owner's approval, the full ad is read
from the job's page (the page a person sees when clicking the job), but only for jobs that
passed the quick relevance check, one page at a time, and never again in that search once
Adzuna refuses.
"""

import dataclasses
import logging
from collections.abc import Iterator

import httpx

from jobcu.countries import COUNTRIES
from jobcu.freshness import days_back, parse_iso, window_start
from jobcu.jobposting import find_job_posting
from jobcu.keystore import KeyStore
from jobcu.keywords import SearchTerm
from jobcu.sources.base import FoundJob, JobQuery, JobSource, SourceContext, SourceError
from jobcu.sources.budget import BudgetExhausted, Limits, RequestBudget, share_of_month
from jobcu.sources.http import Blocked, KeyCheck, client

log = logging.getLogger(__name__)

API = "https://api.adzuna.com/v1/api/jobs"
KEY_APP_ID = "adzuna_app_id"
KEY_APP_KEY = "adzuna_app_key"
COUNTRIES_COVERED = frozenset({"AT", "BE", "CH", "DE", "ES", "FR", "GB", "IT", "NL", "PL"})
PAGE_SIZE = 50
WORDS_PER_REQUEST = 12
# A little below Adzuna's limits (250 a day, 2,500 a month), as a safety margin. How many one
# search may use is worked out from what is left this month (see budget.share_of_month).
LIMITS = Limits(per_day=240, per_month=2400)


class AdzunaSource(JobSource):
    id = "adzuna"
    name = "Adzuna"
    kind = "aggregator"
    countries = COUNTRIES_COVERED

    # Stop reading job pages after this many refusals in a row (one refused ad is normal).
    MAX_REFUSALS_IN_A_ROW = 3

    def __init__(self) -> None:
        self.pages_refused = False
        self._refusals_in_a_row = 0

    def unavailable_reason(self, keys: KeyStore) -> str | None:
        if not keys.get(KEY_APP_ID) or not keys.get(KEY_APP_KEY):
            return "Adzuna: no keys saved in Settings."
        return None

    def load_details(self, job: FoundJob, ctx: SourceContext) -> FoundJob:
        if self.pages_refused or not job.url:
            return job
        try:
            response = ctx.http.get(job.url)
        except Blocked:
            return self._stop_reading_pages(job, ctx)
        except httpx.HTTPError:
            return job
        if response.status_code == 429:
            return self._stop_reading_pages(job, ctx)
        if response.status_code == 403:
            # This ad's page is refused: skip it, never retry it.
            self._refusals_in_a_row += 1
            if self._refusals_in_a_row >= self.MAX_REFUSALS_IN_A_ROW:
                return self._stop_reading_pages(job, ctx)
            return job
        if response.status_code != 200:
            return job
        self._refusals_in_a_row = 0
        posting = find_job_posting(response.text)
        if posting is None or len(posting.description) <= len(job.description):
            return job
        final_host = response.url.host or ""
        return dataclasses.replace(
            job,
            description=posting.description,
            description_is_complete=True,
            job_types=job.job_types or posting.job_types,
            work_mode="remote" if posting.remote else job.work_mode,
            # When the link leads to the employer's own site, that becomes the main link.
            employer_url=None if "adzuna." in final_host else str(response.url),
        )

    def _stop_reading_pages(self, job: FoundJob, ctx: SourceContext) -> FoundJob:
        self.pages_refused = True
        ctx.note(
            "Adzuna didn't allow reading more full ads right now, so some of its jobs were "
            "scored from a short summary."
        )
        return job

    def search(self, query: JobQuery, ctx: SourceContext) -> Iterator[FoundJob]:
        limits = share_of_month(self.id, LIMITS)
        budget = RequestBudget(self.id, self.name, limits)
        credentials = {"app_id": ctx.keys.get(KEY_APP_ID), "app_key": ctx.keys.get(KEY_APP_KEY)}
        start = window_start(query.started_at, query.posted_within_hours)
        countries = [c for c in query.countries if c in COUNTRIES_COVERED]
        locations = [
            (country, place)
            for country in countries
            for place in ([p for p in query.places if p.country == country] or [None])
        ]
        if not locations:
            return
        # Each country or place gets a fair share, so the first one can't use up everything.
        share = max(3, (limits.per_search or 40) // len(locations))
        seen: set[str] = set()
        skipped = 0
        try:
            for country, place in locations:
                used_before = budget.used_this_search
                searches = plan_searches(query.terms, country)
                for number, search in enumerate(searches):
                    if ctx.should_stop():
                        return
                    if budget.used_this_search - used_before >= share:
                        skipped += len(searches) - number
                        break
                    yield from self._run(search, country, place, credentials, start,
                                         query, budget, ctx, seen)
        except BudgetExhausted as exc:
            ctx.report.status = "partial"
            ctx.report.message = exc.message
            return
        if skipped:
            ctx.report.message = (
                f"Adzuna: {skipped} less important search words were left out to stay within its "
                "free daily limit."
            )

    def _run(self, search, country, place, credentials, start, query, budget, ctx, seen):
        page = 1
        while True:
            params = {
                **credentials,
                **search,
                "results_per_page": PAGE_SIZE,
                "max_days_old": days_back(query.posted_within_hours),
                "sort_by": "date",
                "content-type": "application/json",
            }
            if place is not None:
                params["where"] = place.local_name
                params["distance"] = round(place.radius_km or 25)
            budget.spend()
            ctx.report.requests += 1
            try:
                response = ctx.http.get(f"{API}/{country.lower()}/search/{page}", params=params)
            except httpx.HTTPError as exc:
                raise SourceError("Adzuna couldn't be reached.") from exc
            if response.status_code in (401, 403):
                raise SourceError("Adzuna didn't accept the keys. Check them in Settings.")
            if response.status_code == 429:
                raise BudgetExhausted("Adzuna: its usage limit is reached for now.")
            if response.status_code != 200:
                raise SourceError(f"Adzuna answered with a problem (code {response.status_code}).")
            results = response.json().get("results") or []
            too_old = False
            for item in results:
                job = to_found_job(item, country)
                if job.posted_at is not None and job.posted_at < start:
                    too_old = True  # newest first: everything after this is older still
                    break
                if job.source_job_id not in seen:
                    seen.add(job.source_job_id)
                    yield job
            if too_old or len(results) < PAGE_SIZE:
                return
            page += 1


def plan_searches(terms: list[SearchTerm], country: str) -> list[dict]:
    """The Adzuna requests for one country, most valuable first."""
    languages = ["en", *COUNTRIES[country].ad_languages]
    relevant = [t for t in terms if t.language in languages]
    single = list(dict.fromkeys(t.text for t in relevant if " " not in t.text.strip()))
    searches: list[dict] = [
        {"what_or": " ".join(single[i : i + WORDS_PER_REQUEST])}
        for i in range(0, len(single), WORDS_PER_REQUEST)
    ]
    phrases = [t for t in relevant if " " in t.text.strip()]
    phrases.sort(key=lambda t: t.kind != "field_or_skill")
    for text in dict.fromkeys(t.text for t in phrases):
        searches.append({"what_phrase": text})
    return searches


_CONTRACT_TYPES = {
    ("permanent", "full_time"): ["full_time_permanent"],
    ("permanent", "part_time"): ["part_time"],
    ("permanent", None): ["full_time_permanent", "part_time"],
    ("contract", "full_time"): ["fixed_term", "freelance_or_contract"],
    ("contract", "part_time"): ["part_time"],
    ("contract", None): ["fixed_term", "freelance_or_contract", "part_time"],
    (None, "part_time"): ["part_time"],
}


def to_found_job(item: dict, country: str) -> FoundJob:
    location = item.get("location") or {}
    salary = None
    if item.get("salary_min") and item.get("salary_is_predicted") in ("0", 0, None):
        high = item.get("salary_max")
        salary = f"{item['salary_min']:,.0f}" + (f" – {high:,.0f}" if high else "")
    return FoundJob(
        source="adzuna",
        source_job_id=str(item.get("id")),
        url=item.get("redirect_url") or "",
        title=(item.get("title") or "").strip(),
        company=((item.get("company") or {}).get("display_name") or None),
        location_text=location.get("display_name"),
        country=country,
        latitude=item.get("latitude"),
        longitude=item.get("longitude"),
        posted_at=parse_iso(item.get("created")),
        date_precision="exact" if item.get("created") else "unknown",
        description=(item.get("description") or "").strip(),
        description_is_complete=False,  # Adzuna sends only the start of the ad
        job_types=_CONTRACT_TYPES.get((item.get("contract_type"), item.get("contract_time")), []),
        salary_text=salary,
    )


def check_keys(keys: KeyStore) -> KeyCheck:
    app_id, app_key = keys.get(KEY_APP_ID), keys.get(KEY_APP_KEY)
    if not app_id or not app_key:
        return KeyCheck(False, "Please save both the Application ID and the Application Key.")
    try:
        with client() as http:
            response = http.get(
                f"{API}/gb/search/1",
                params={"app_id": app_id, "app_key": app_key, "results_per_page": 1},
            )
    except httpx.HTTPError as exc:
        # The request address contains the key, so only the error type is logged.
        log.warning("Adzuna key check failed: %s", type(exc).__name__)
        return KeyCheck(False, "Jobcu couldn't reach Adzuna. Check your internet connection.")
    if response.status_code == 200:
        return KeyCheck(True, "Adzuna keys work.")
    if response.status_code in (401, 403):
        return KeyCheck(
            False,
            "Adzuna didn't accept these keys. Check that the Application ID and Application Key "
            "are copied completely and not swapped.",
        )
    if response.status_code == 429:
        return KeyCheck(False, "Adzuna says its usage limit is reached. Try again later.")
    return KeyCheck(
        False, f"Adzuna answered with an unexpected problem (code {response.status_code})."
    )
