"""prospective.ch career sites (Swiss), with made-up employers and answers."""

from datetime import UTC, datetime

import httpx

from jobcu.keystore import KeyStore
from jobcu.sources import all_sources, prospective
from jobcu.sources.base import SourceContext, SourceReport
from jobcu.sources.careers import Employer
from jobcu.sources.http import PoliteClient

EMPLOYER = Employer("Kanton Beispiel", "prospective", "1234", ("CH",))


def job(number, title="Pflegefachfrau/-mann HF 80-100%", city="Liestal", country="Schweiz",
        low="80", high="100"):
    szas = {"sza_tasks": "<ul><li>Pflege von Patientinnen</li></ul>",
            "sza_requirements": "<p>Diplom HF Pflege</p>", "sza_benefits": "<p>Gute Lage</p>",
            "sza_pensum.min": low, "sza_pensum.max": high}
    if city:
        szas["sza_location.city"] = city
    if country:
        szas["sza_location.country"] = country
    return {"id": str(number), "title": title, "start_date": "2026-09-24T09:10:33Z",
            "language": "de", "szas": szas, "attributes": {},
            "links": {"directlink": f"https://jobs.beispiel.ch/offene-stellen/{number}"}}


def context(handler):
    http = PoliteClient(min_intervals={}, sleep=lambda s: None,
                        transport=httpx.MockTransport(handler))
    return SourceContext(http, KeyStore(), SourceReport("prospective", "prospective.ch"),
                         lambda: False, lambda message: None)


def test_reads_every_page_of_an_employers_jobs():
    asked = []

    def handler(request):
        offset = int(request.url.params["offset"])
        asked.append(offset)
        assert request.url.path == "/public/v1/medium/1234/jobs"
        count = 100 if offset == 0 else 3
        return httpx.Response(200, json={"total": 103, "jobs": [
            job(offset + n) for n in range(count)]})

    jobs = list(prospective.ProspectiveSource().list_jobs(EMPLOYER, context(handler)))
    assert asked == [0, 100] and len(jobs) == 103
    first = jobs[0]
    assert first.url == "https://jobs.beispiel.ch/offene-stellen/0"
    assert first.company == "Kanton Beispiel"
    assert first.location_text == "Liestal, Schweiz" and first.country == "CH"
    assert first.posted_at == datetime(2026, 9, 24, 9, 10, 33, tzinfo=UTC)
    assert first.description_is_complete
    assert first.description.startswith("Workload: 80-100 %")
    assert "• Pflege von Patientinnen" in first.description
    assert "Diplom HF Pflege" in first.description


def test_workload_and_title_give_the_job_types():
    def types(**extra):
        return prospective.to_found_job(job(1, **extra), EMPLOYER).job_types

    assert types(low="100", high="100") == ["full_time_permanent"]
    assert types(low="80", high="100") == ["full_time_permanent", "part_time"]
    assert types(low="50", high="60") == ["part_time"]
    assert types(title="Sachbearbeiter/in 100% (befristet)", low="100", high="100") == [
        "fixed_term"]
    assert types(title="Praktikant:in 60%", low="60", high="60") == [
        "internship_or_working_student", "part_time"]


def test_places_and_countries():
    no_place = prospective.to_found_job(job(1, city="", country=""), EMPLOYER)
    assert no_place.location_text is None and no_place.country == "CH"
    abroad = prospective.to_found_job(job(2, city="Berlin", country="Deutschland"), EMPLOYER)
    assert abroad.country == "DE"
    repeated = prospective.to_found_job(job(3, city="Santiago de Chile, Chile", country="Chile"),
                                        EMPLOYER)
    assert repeated.location_text == "Santiago de Chile, Chile" and repeated.country is None


def test_it_is_one_of_the_career_systems_and_the_directory_has_its_employers():
    assert any(isinstance(source, prospective.ProspectiveSource) for source in all_sources())
    source = prospective.ProspectiveSource()
    assert len(source.employers(["CH"])) >= 5
