"""NAV Arbeidsplassen: Norway's public employment service and its job ad feed, checked
2026-09-24.

NAV's stilling-feed lists every new or changed job ad in Norway (about 2,400 entries a day),
1,000 an answer, with the title, employer, municipality and status. Jobcu asks for the entries
changed since the window began, matches the titles on its own side, and reads the matching
ads' full entries: the ad, the dates, the places, the contract and hours, and the employer's
own application link. "Everyone can use the service" (NAV's terms, arbeidsplassen.nav.no/
vilkar-api); ads must be shown only while active, and applications must link straight to the
employer's system, which the job's main link does. The contacts in an ad are personal data and
are never kept.

A public token for the feed is published by NAV and rotates now and then, so it's fetched for
each search.
"""

from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta
from email.utils import format_datetime
from zoneinfo import ZoneInfo

import httpx

from jobcu.freshness import day_at_utc, end_of_day, freshness, parse_iso, window_start
from jobcu.sources.base import FoundJob, JobQuery, JobSource, SourceContext, SourceError
from jobcu.sources.budget import BudgetExhausted, Limits, RequestBudget
from jobcu.sources.matching import matches_places, matches_terms
from jobcu.text import html_to_text, tidy

SITE = "https://pam-stilling-feed.nav.no"
TOKEN = f"{SITE}/api/publicToken"
FEED = f"{SITE}/api/v1/feed"
LIMITS = Limits(per_search=150)
MAX_FEED_PAGES = 20  # 1,000 entries each; a week is about 17,000
NORWEGIAN_TIME = ZoneInfo("Europe/Oslo")

# NAV's engagement types. "Fast" (permanent) gets its hours from "extent".
_ENGAGEMENTS = {
    "fast": [],
    "vikariat": ["fixed_term"],
    "engasjement": ["fixed_term"],
    "prosjekt": ["fixed_term"],
    "sesong": ["fixed_term"],
    "åremål": ["fixed_term"],
    "lærling": ["internship_or_working_student"],
    "trainee": ["internship_or_working_student"],
    "sommerjobb": ["fixed_term"],
    "selvstendig næringsdrivende": ["freelance_or_contract"],
    "frilanser": ["freelance_or_contract"],
}


class NavSource(JobSource):
    id = "nav"
    name = "NAV Arbeidsplassen (Norway)"
    kind = "job_board"
    countries = frozenset({"NO"})

    def search(self, query: JobQuery, ctx: SourceContext) -> Iterator[FoundJob]:
        budget = RequestBudget(self.id, self.name, LIMITS)
        start = window_start(query.started_at, query.posted_within_hours)
        languages = {"en", "no"}
        seen: set[str] = set()  # an ad changed twice is in the feed twice
        try:
            token = self._token(budget, ctx)
            for entry in self._changed_since(start, token, budget, ctx):
                if ctx.should_stop():
                    return
                if entry["uuid"] in seen:
                    continue
                seen.add(entry["uuid"])
                if not matches_terms(query.terms, languages, entry.get("title") or ""):
                    continue
                job = self._full_entry(entry["uuid"], token, budget, ctx)
                if job is None or job.country not in query.countries:
                    continue
                if freshness(job.posted_at, job.date_precision, start) == "too_old":
                    continue
                if matches_places(query.places, job.country, job.location_text):
                    yield job
        except BudgetExhausted as exc:
            ctx.report.status = "partial"
            ctx.report.message = exc.message

    def _token(self, budget: RequestBudget, ctx: SourceContext) -> str:
        text = self._get(TOKEN, budget, ctx, token=None).text
        found = [word for word in text.split() if word.count(".") == 2]
        if not found:
            raise SourceError("NAV's feed didn't give its public access token.")
        return found[-1]

    def _changed_since(self, start: datetime, token: str, budget: RequestBudget,
                       ctx: SourceContext) -> Iterator[dict]:
        """Active entries changed since the window began (an ad posted in it changed in it)."""
        since = format_datetime(start - timedelta(minutes=5), usegmt=True)
        response = self._get(FEED, budget, ctx, token=token,
                             headers={"If-Modified-Since": since})
        for _ in range(MAX_FEED_PAGES):
            if response.status_code == 304:
                return
            data = response.json()
            for item in data.get("items") or []:
                entry = item.get("_feed_entry") or {}
                if entry.get("status") == "ACTIVE" and entry.get("uuid"):
                    yield {**entry, "title": tidy(entry.get("title") or item.get("title") or "")}
            next_url = data.get("next_url")
            if not next_url or not data.get("items"):
                return
            response = self._get(SITE + next_url, budget, ctx, token=token)

    def _full_entry(self, uuid: str, token: str, budget: RequestBudget,
                    ctx: SourceContext) -> FoundJob | None:
        try:
            entry = self._get(f"{SITE}/api/v1/feedentry/{uuid}", budget, ctx, token=token).json()
        except (SourceError, ValueError):
            return None
        if entry.get("status") not in (None, "ACTIVE"):
            return None
        return to_found_job(entry.get("ad_content") or {})

    def _get(self, url: str, budget: RequestBudget, ctx: SourceContext, *, token: str | None,
             headers: dict | None = None) -> httpx.Response:
        budget.spend()
        ctx.report.requests += 1
        headers = dict(headers or {})
        if token:
            headers["Authorization"] = f"Bearer {token}"
        try:
            response = ctx.http.get(url, headers=headers, cache=False)
        except httpx.HTTPError as exc:
            raise SourceError("NAV's job feed couldn't be reached.") from exc
        if response.status_code == 429:
            raise BudgetExhausted("NAV's job feed asked Jobcu to slow down for now.")
        if response.status_code not in (200, 304):
            raise SourceError(
                f"NAV's job feed answered with a problem (code {response.status_code}).")
        return response


def _norwegian_day(text: str | None) -> tuple[datetime | None, str]:
    """ "2026-09-24T00:00:00+02:00": midnight means only the day is known."""
    value = parse_iso(text)
    if value is None:
        return None, "unknown"
    local = value.astimezone(NORWEGIAN_TIME)
    if (local.hour, local.minute, local.second) == (0, 0, 0):
        return day_at_utc(local.date()), "day"
    return value.astimezone(UTC), "exact"


def _closing(text: str | None) -> datetime | None:
    """The application deadline, a day in Norway: open until its end. Some ads say "snarest"
    (as soon as possible) instead, which gives no date."""
    try:
        return end_of_day(date.fromisoformat((text or "")[:10]), NORWEGIAN_TIME)
    except ValueError:
        return None


def _places(locations: list) -> tuple[str | None, str | None]:
    towns, countries = [], set()
    for place in locations or []:
        if not isinstance(place, dict):
            continue
        town = place.get("city") or place.get("municipal") or place.get("county") or ""
        town = town.title() if town.isupper() else town
        if town and town not in towns:
            towns.append(town)
        country = (place.get("country") or "NORGE").strip().upper()
        countries.add("NO" if country in ("NORGE", "NORWAY", "NOREG") else "other")
    country = "NO" if countries in ({"NO"}, set()) else None
    return ", ".join(towns) or None, country


def _job_types(engagement: str, extent: str) -> list[str]:
    types = list(_ENGAGEMENTS.get(engagement.strip().lower(), []))
    if engagement.strip().lower() == "fast" and "heltid" in extent.lower():
        types.append("full_time_permanent")
    if "deltid" in extent.lower() and "part_time" not in types:
        types.append("part_time")
    return types


def to_found_job(ad: dict) -> FoundJob | None:
    uuid, title = ad.get("uuid"), tidy(ad.get("title") or "")
    if not uuid or not title:
        return None
    location, country = _places(ad.get("workLocations") or [])
    posted, precision = _norwegian_day(ad.get("published"))
    employer = ad.get("employer") or {}
    apply_url = (ad.get("applicationUrl") or "").strip()
    engagement, extent = str(ad.get("engagementtype") or ""), str(ad.get("extent") or "")
    facts = [f"Stilling: {ad['jobtitle']}" if ad.get("jobtitle") else "",
             f"Ansettelsesform: {engagement}" if engagement else "",
             f"Omfang: {extent}" if extent else "",
             f"Søknadsfrist: {ad['applicationDue']}" if ad.get("applicationDue") else ""]
    return FoundJob(
        source="nav",
        source_job_id=str(uuid),
        url=ad.get("link") or f"https://arbeidsplassen.nav.no/stillinger/stilling/{uuid}",
        title=title,
        company=tidy(employer.get("name") or "") or None,
        location_text=location,
        country=country,
        posted_at=posted,
        date_precision=precision,
        description=tidy("\n".join(f for f in facts if f) + "\n\n"
                         + html_to_text(ad.get("description") or "")),
        description_is_complete=bool(ad.get("description")),
        job_types=_job_types(engagement, extent),
        employer_url=apply_url if apply_url.startswith(("https://", "http://")) else None,
        closes_at=_closing(ad.get("applicationDue")),
    )
