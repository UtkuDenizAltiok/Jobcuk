"""Bundesagentur für Arbeit (Jobsuche): Germany's largest job database.

There is no official API; this uses the public endpoint documented by the community
project github.com/bundesAPI/jobsuche-api (HANDOVER section 9.2). It may change
without notice, so failures are reported plainly and never break a search.

It gives the date a job was **first** published, which catches reposted old jobs.
"""

import base64
import logging
from collections.abc import Iterator
from datetime import date

import httpx

from jobcu.countries import COUNTRIES
from jobcu.freshness import day_at_utc, days_back, freshness, window_start
from jobcu.sources.base import FoundJob, JobQuery, JobSource, SourceContext, SourceError
from jobcu.sources.budget import BudgetExhausted, Limits, RequestBudget
from jobcu.text import html_to_text

log = logging.getLogger(__name__)

API = "https://rest.arbeitsagentur.de/jobboerse/jobsuche-service"
# Not a secret: the public client ID the agency's own website uses for everyone.
HEADERS = {"X-API-Key": "jobboerse-jobsuche"}  # jobcu-guard: allow
PAGE_SIZE = 100
MAX_PAGES_PER_WORD = 5
DEFAULT_RADIUS_KM = 25
LIMITS = Limits(per_search=400)


class BundesagenturSource(JobSource):
    id = "bundesagentur"
    name = "Bundesagentur für Arbeit"
    kind = "job_board"
    countries = frozenset({"DE"})

    def search(self, query: JobQuery, ctx: SourceContext) -> Iterator[FoundJob]:
        self._budget = RequestBudget(self.id, self.name, LIMITS)
        start = window_start(query.started_at, query.posted_within_hours)
        languages = {"en", *COUNTRIES["DE"].ad_languages}
        words = list(dict.fromkeys(t.text for t in query.terms if t.language in languages))
        places = [p for p in query.places if p.country == "DE"] or [None]
        seen: set[str] = set()
        try:
            for place in places:
                for word in words:
                    if ctx.should_stop():
                        return
                    for item in self._search_word(word, place, query, self._budget, ctx):
                        posted = _parse_day(item.get("datumErsteVeroeffentlichung"))
                        if freshness(posted, "day" if posted else "unknown", start) == "too_old":
                            continue
                        ref = item.get("referenznummer")
                        if ref and ref not in seen:
                            seen.add(ref)
                            yield to_found_job(item)
        except BudgetExhausted as exc:
            ctx.report.status = "partial"
            ctx.report.message = exc.message

    def load_details(self, job: FoundJob, ctx: SourceContext) -> FoundJob:
        budget = getattr(self, "_budget", None) or RequestBudget(self.id, self.name, LIMITS)
        code = base64.b64encode(job.source_job_id.encode()).decode()
        try:
            details = self._get(f"{API}/pc/v4/jobdetails/{code}", {}, budget, ctx)
        except (SourceError, BudgetExhausted):
            return job
        return to_found_job({"referenznummer": job.source_job_id}, details)

    def _search_word(self, word, place, query, budget, ctx) -> Iterator[dict]:
        for page in range(1, MAX_PAGES_PER_WORD + 1):
            params = {
                "was": word,
                "veroeffentlichtseit": days_back(query.posted_within_hours),
                "size": PAGE_SIZE,
                "page": page,
            }
            if place is not None:
                params["wo"] = place.local_name
                params["umkreis"] = round(place.radius_km or DEFAULT_RADIUS_KM)
            data = self._get(f"{API}/pc/v6/jobs", params, budget, ctx)
            results = data.get("ergebnisliste") or []
            yield from results
            if len(results) < PAGE_SIZE or page * PAGE_SIZE >= (data.get("maxErgebnisse") or 0):
                return

    def _get(self, url, params, budget, ctx) -> dict:
        budget.spend()
        ctx.report.requests += 1
        try:
            response = ctx.http.get(url, params=params, headers=HEADERS)
        except httpx.HTTPError as exc:
            raise SourceError("The Bundesagentur für Arbeit couldn't be reached.") from exc
        if response.status_code == 429:
            raise BudgetExhausted("Bundesagentur für Arbeit: asked Jobcu to slow down for now.")
        if response.status_code != 200:
            raise SourceError(
                "The Bundesagentur für Arbeit answered with a problem "
                f"(code {response.status_code}). Its public interface may have changed."
            )
        return response.json()


# The agency also lists jobs abroad; its addresses name the country in German.
_COUNTRY_NAMES = {
    "DEUTSCHLAND": "DE", "ÖSTERREICH": "AT", "OESTERREICH": "AT", "SCHWEIZ": "CH",
    "NIEDERLANDE": "NL", "BELGIEN": "BE", "LUXEMBURG": "LU", "FRANKREICH": "FR",
    "DÄNEMARK": "DK", "POLEN": "PL", "TSCHECHIEN": "CZ", "TSCHECHISCHE REPUBLIK": "CZ",
    "ITALIEN": "IT", "SPANIEN": "ES", "PORTUGAL": "PT", "IRLAND": "IE",
    "VEREINIGTES KÖNIGREICH": "GB", "GROSSBRITANNIEN": "GB", "SCHWEDEN": "SE",
    "NORWEGEN": "NO", "FINNLAND": "FI", "ISLAND": "IS", "UNGARN": "HU", "SLOWAKEI": "SK",
    "SLOWENIEN": "SI", "KROATIEN": "HR", "RUMÄNIEN": "RO", "BULGARIEN": "BG",
    "GRIECHENLAND": "GR", "ZYPERN": "CY", "MALTA": "MT", "ESTLAND": "EE", "LETTLAND": "LV",
    "LITAUEN": "LT", "LIECHTENSTEIN": "LI",
}


def _parse_day(text: str | None):
    try:
        return day_at_utc(date.fromisoformat(text or ""))
    except ValueError:
        return None


def _job_types(item: dict) -> list[str]:
    kind = (item.get("stellenangebotsart") or "").upper()
    if kind == "SELBSTAENDIGKEIT":
        return ["freelance_or_contract"]
    if kind in ("PRAKTIKUM_TRAINEE", "AUSBILDUNG"):
        return ["internship_or_working_student"]
    if kind != "ARBEIT":
        return []
    full_time = item.get("arbeitszeitVollzeit")
    duration = (item.get("vertragsdauer") or "").upper()
    if duration == "BEFRISTET":
        return ["fixed_term"] if full_time else ["fixed_term", "part_time"]
    if duration == "UNBEFRISTET":
        return ["full_time_permanent"] if full_time else ["full_time_permanent", "part_time"]
    return []


# Some jobs give only their state, as a code ("BADEN_WUERTTEMBERG"): shown and matched by name.
_STATES = {
    "BADEN_WUERTTEMBERG": "Baden-Württemberg", "BAYERN": "Bayern", "BERLIN": "Berlin",
    "BRANDENBURG": "Brandenburg", "BREMEN": "Bremen", "HAMBURG": "Hamburg", "HESSEN": "Hessen",
    "MECKLENBURG_VORPOMMERN": "Mecklenburg-Vorpommern", "NIEDERSACHSEN": "Niedersachsen",
    "NORDRHEIN_WESTFALEN": "Nordrhein-Westfalen", "RHEINLAND_PFALZ": "Rheinland-Pfalz",
    "SAARLAND": "Saarland", "SACHSEN": "Sachsen", "SACHSEN_ANHALT": "Sachsen-Anhalt",
    "SCHLESWIG_HOLSTEIN": "Schleswig-Holstein", "THUERINGEN": "Thüringen",
}


def state_name(code: str | None) -> str | None:
    """"BADEN_WUERTTEMBERG" → "Baden-Württemberg"; anything else as it came, made readable."""
    if not code:
        return None
    return _STATES.get(code.upper(), code.replace("_", " ").title() if code.isupper() else code)


def to_found_job(item: dict, details: dict | None = None) -> FoundJob:
    source = details or item
    ref = item.get("referenznummer") or ""
    places = source.get("stellenlokationen") or []
    first = places[0] if places else {}
    address = first.get("adresse") or {}
    towns = list(dict.fromkeys(
        (p.get("adresse") or {}).get("ort") for p in places if (p.get("adresse") or {}).get("ort")
    ))
    posted = _parse_day(source.get("datumErsteVeroeffentlichung"))
    low, high = source.get("gehaltsspanneVon"), source.get("gehaltsspanneBis")
    salary = f"€{low:,.0f}" + (f" – €{high:,.0f}" if high else "") if low else None
    country = _COUNTRY_NAMES.get((address.get("land") or "").upper())
    return FoundJob(
        source="bundesagentur",
        source_job_id=ref,
        url=f"https://www.arbeitsagentur.de/jobsuche/jobdetail/{ref}",
        title=(source.get("stellenangebotsTitel") or "").strip(),
        company=source.get("firma") or None,
        location_text=", ".join(towns) or state_name(address.get("region")),
        country=country,
        latitude=first.get("breite"),
        longitude=first.get("laenge"),
        posted_at=posted,
        date_precision="day" if posted else "unknown",
        description=html_to_text(source.get("stellenangebotsBeschreibung")),
        description_is_complete=details is not None,
        job_types=_job_types(source),
        salary_text=salary,
    )
