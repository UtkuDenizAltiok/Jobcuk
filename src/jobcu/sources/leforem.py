"""Le Forem's open data: every job offer Wallonia's public employment service distributes,
checked 2026-09-24.

Le Forem publishes its offers as open data (CC BY-SA 4.0), updated in real time: about 26,000
live offers and 1,200 new a day, not only in Wallonia but also in Flanders and Brussels, among
them the offers of Jobat, StepStone Belgium and the big staffing agencies. One request exports
every offer published since the window began; Jobcu matches the titles and places itself.

The data has no ad text, but it says what the ad asks in a structured way: the occupation,
the contract and hours, the languages, the driving licence, the level of education and the
experience. That becomes the job's summary; the best jobs are read online by the person's AI,
as for other summaries. Le Forem's own job pages are closed to robots, so Jobcu never opens
them; the person does, through the job's link.
"""

import math
from collections.abc import Iterator
from datetime import date, timedelta
from zoneinfo import ZoneInfo

import httpx

from jobcu.freshness import day_at_utc, freshness, window_start
from jobcu.sources.base import FoundJob, JobQuery, JobSource, SourceContext, SourceError
from jobcu.sources.matching import matches_places, matches_terms
from jobcu.text import tidy

EXPORT = ("https://leforem-digitalwallonia.opendatasoft.com/api/explore/v2.1/catalog/datasets/"
          "offres-d-emploi-forem/exports/json")
FIELDS = ("numerooffreforem,titreoffre,lieuxtravaillocalite,lieuxtravailregionnuts,"
          "lieuxtravailgeo,typecontrat,nomemployeur,regimetravail,niveauxetudes,langues,"
          "experiencerequise,permisdeconduire,secteurs,metier,url,datedebutdiffusion,source")
BELGIAN_TIME = ZoneInfo("Europe/Brussels")

# Le Forem's contract types. Temporary agency work "with an option" of a permanent contract is
# shown to people who want either; a part-time regime is added from the hours.
_CONTRACTS = {
    "durée indéterminée": ["full_time_permanent"],
    "salarié statutaire": ["full_time_permanent"],
    "intérimaire avec option sur durée indéterminée": ["fixed_term", "full_time_permanent"],
    "intérimaire": ["fixed_term"],
    "durée déterminée": ["fixed_term"],
    "remplacement": ["fixed_term"],
    "nettement défini": ["fixed_term"],
    "journalier (occasionnel ou saisonnier)": ["fixed_term"],
    "etudiant": ["internship_or_working_student"],
    "contrat d'apprentissage": ["internship_or_working_student"],
    "stage": ["internship_or_working_student"],
    "flexi-jobs": ["part_time"],
    "contrat collaboration indépendant": ["freelance_or_contract"],
}


class LeForemSource(JobSource):
    id = "leforem"
    name = "Le Forem (Belgium)"
    kind = "job_board"
    countries = frozenset({"BE"})

    def search(self, query: JobQuery, ctx: SourceContext) -> Iterator[FoundJob]:
        start = window_start(query.started_at, query.posted_within_hours)
        # Dates are days in Belgium; a day's margin keeps every day the window touches.
        first_day = start.astimezone(BELGIAN_TIME).date() - timedelta(days=1)
        languages = {"en", "fr", "nl", "de"}
        for offer in self._export(first_day, ctx):
            job = to_found_job(offer)
            if job is None or job.country not in query.countries:
                continue
            if freshness(job.posted_at, job.date_precision, start) == "too_old":
                continue
            if not matches_terms(query.terms, languages, job.title, job.description):
                continue
            if matches_places(query.places, job.country, job.location_text):
                yield job

    def _export(self, first_day: date, ctx: SourceContext) -> list[dict]:
        ctx.report.requests += 1
        params = {"where": f"datedebutdiffusion>=date'{first_day.isoformat()}'",
                  "select": FIELDS, "order_by": "datedebutdiffusion desc"}
        try:
            response = ctx.http.get(EXPORT, params=params, cache=False)
        except httpx.HTTPError as exc:
            raise SourceError("Le Forem's open data couldn't be reached.") from exc
        if response.status_code != 200:
            raise SourceError(
                f"Le Forem's open data answered with a problem (code {response.status_code})."
            )
        try:
            offers = response.json()
        except ValueError as exc:
            raise SourceError("Le Forem's open data didn't answer with a job list.") from exc
        return offers if isinstance(offers, list) else []


def _listed(value) -> list[str]:
    if isinstance(value, list):
        return [tidy(str(item)) for item in value if item]
    return [tidy(str(value))] if value else []


def _job_types(contract: str, hours: str) -> list[str]:
    types = list(_CONTRACTS.get(contract.strip().lower(), []))
    if "partiel" in hours.lower():
        types = [t for t in types if t != "full_time_permanent"]
        if "part_time" not in types:
            types.append("part_time")
    return types


def _summary(offer: dict) -> str:
    """What the offer asks, in plain lines (labels in English, values as Le Forem gives them)."""
    lines = [
        ("Occupation", _listed(offer.get("metier"))),
        ("Contract", _listed(offer.get("typecontrat")) + _listed(offer.get("regimetravail"))),
        ("Languages asked", _listed(offer.get("langues"))),
        ("Driving licence", _listed(offer.get("permisdeconduire"))),
        ("Education", _listed(offer.get("niveauxetudes"))),
        ("Experience asked in", _listed(offer.get("experiencerequise"))),
        ("Sector", _listed(offer.get("secteurs"))),
        ("Published through", _listed(offer.get("source"))),
    ]
    text = "\n".join(f"{label}: {', '.join(values)}" for label, values in lines if values)
    return f"{text}\n(Summary from Le Forem's open data; the full ad is on the job's page.)"


def to_found_job(offer: dict) -> FoundJob | None:
    number, title = str(offer.get("numerooffreforem") or ""), tidy(offer.get("titreoffre") or "")
    if not number or not title:
        return None
    nuts = _listed(offer.get("lieuxtravailregionnuts"))
    country = nuts[0][:2].upper() if nuts else "BE"
    towns = [town.title() if town.isupper() else town
             for town in _listed(offer.get("lieuxtravaillocalite"))]
    points = offer.get("lieuxtravailgeo") or []
    point = points[0] if isinstance(points, list) and points else {}
    try:
        posted = day_at_utc(date.fromisoformat(str(offer.get("datedebutdiffusion"))[:10]))
    except ValueError:
        posted = None
    latitude, longitude = point.get("lat"), point.get("lon")
    return FoundJob(
        source="leforem",
        source_job_id=number,
        url=offer.get("url") or f"https://www.leforem.be/recherche-offres/offre-detail/{number}",
        title=title,
        company=tidy(offer.get("nomemployeur") or "") or None,
        location_text=", ".join(dict.fromkeys(towns)) or None,
        country=country,
        latitude=latitude if isinstance(latitude, (int, float)) and math.isfinite(latitude)
        else None,
        longitude=longitude if isinstance(longitude, (int, float)) and math.isfinite(longitude)
        else None,
        posted_at=posted,
        date_precision="day" if posted else "unknown",
        description=_summary(offer),
        job_types=_job_types(str(offer.get("typecontrat") or ""),
                             str(offer.get("regimetravail") or "")),
    )
