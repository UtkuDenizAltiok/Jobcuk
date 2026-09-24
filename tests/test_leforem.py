"""Le Forem's open data export, with made-up offers (never the real site)."""

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import httpx

from jobcu.keystore import KeyStore
from jobcu.keywords import SearchTerm
from jobcu.location import Place
from jobcu.sources import leforem
from jobcu.sources.base import JobQuery, SourceContext, SourceReport
from jobcu.sources.http import PoliteClient

NOW = datetime.now(UTC)
TODAY = NOW.astimezone(ZoneInfo("Europe/Brussels")).date()


def term(text, language="fr", kind="job_title"):
    return SearchTerm(text=text, language=language, kind=kind)


def offer(number, title, days_ago=0, town="NAMUR", nuts=("BE", "BE35"),
          contract="Durée indéterminée", hours="Temps plein", **extra):
    return {
        "numerooffreforem": number, "titreoffre": title, "lieuxtravaillocalite": [town],
        "lieuxtravailregionnuts": list(nuts), "lieuxtravailgeo": [{"lon": 4.87, "lat": 50.47}],
        "typecontrat": contract, "nomemployeur": "Hôpital Exemple", "regimetravail": hours,
        "niveauxetudes": ["Bachelier"], "langues": ["Français", "Néerlandais"],
        "experiencerequise": None, "permisdeconduire": ["B"],
        "secteurs": ["Activités des hôpitaux"], "metier": "Infirmier / Infirmière",
        "url": f"https://www.leforem.be/recherche-offres/offre-detail/{number}",
        "datedebutdiffusion": (TODAY - timedelta(days=days_ago)).isoformat(),
        "source": "Via site Forem", **extra,
    }


def context(handler):
    http = PoliteClient(min_intervals={}, sleep=lambda s: None,
                        transport=httpx.MockTransport(handler))
    return SourceContext(http, KeyStore(), SourceReport("leforem", "Le Forem"),
                         lambda: False, lambda message: None)


def query(terms, hours=24, places=(), countries=("BE",)):
    return JobQuery(countries=list(countries), places=list(places), terms=terms,
                    posted_within_hours=hours, started_at=NOW)


def test_one_export_brings_the_window_and_the_matching_offers_are_kept():
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json=[
            offer("1", "Infirmier en soins intensifs (H/F/X)"),
            offer("2", "Verpleegkundige intensieve zorg", town="GENT", nuts=("BE", "BE23")),
            offer("3", "Comptable (H/F/X)"),  # not what was searched
            offer("4", "Infirmier (H/F/X)", days_ago=5),  # older than the window
            offer("5", "Infirmier (H/F/X)", town="LONGWY", nuts=("FR", "FRF3")),  # France
        ])

    terms = [term("Infirmier"), term("Verpleegkundige", "nl")]
    jobs = list(leforem.LeForemSource().search(query(terms), context(handler)))
    assert [job.source_job_id for job in jobs] == ["1", "2"]
    assert len(requests) == 1
    where = requests[0].url.params["where"]
    assert where.startswith("datedebutdiffusion>=date'")
    first = jobs[0]
    assert first.location_text == "Namur" and first.country == "BE"
    assert (first.latitude, first.longitude) == (50.47, 4.87)
    assert first.company == "Hôpital Exemple" and first.date_precision == "day"
    assert first.job_types == ["full_time_permanent"]
    assert "Languages asked: Français, Néerlandais" in first.description
    assert "Driving licence: B" in first.description
    assert not first.description_is_complete
    assert jobs[1].location_text == "Gent"


def test_contract_types_and_hours_become_job_types():
    assert leforem._job_types("Intérimaire avec option sur durée indéterminée", "Temps plein") == [
        "fixed_term", "full_time_permanent"]
    assert leforem._job_types("Durée indéterminée", "Temps partiel") == ["part_time"]
    assert leforem._job_types("Durée déterminée", "Temps partiel") == ["fixed_term", "part_time"]
    assert leforem._job_types("Etudiant", "Temps plein") == ["internship_or_working_student"]
    assert leforem._job_types("Something new", "Temps plein") == []


def test_named_places_are_matched():
    def handler(request):
        return httpx.Response(200, json=[
            offer("1", "Infirmier", town="LIEGE"), offer("2", "Infirmier", town="ARLON")])

    liege = Place(name="Liège", local_name="Liège", country="BE", kind="city", radius_km=None)
    jobs = list(leforem.LeForemSource().search(query([term("Infirmier")], places=[liege]),
                                               context(handler)))
    assert [job.source_job_id for job in jobs] == ["1"]


def test_a_failing_export_fails_only_this_source():
    ctx = context(lambda request: httpx.Response(503, text="down"))
    try:
        list(leforem.LeForemSource().search(query([term("Infirmier")]), ctx))
    except leforem.SourceError as exc:
        assert "Le Forem" in str(exc)
    else:
        raise AssertionError("a failing export should raise SourceError")
