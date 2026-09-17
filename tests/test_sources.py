from datetime import UTC, datetime, timedelta

import httpx
import pytest

from jobcu.keystore import KeyStore
from jobcu.keywords import SearchTerm
from jobcu.location import Place
from jobcu.sources import adzuna, bundesagentur, reed
from jobcu.sources.base import JobQuery, SourceContext, SourceError, SourceReport
from jobcu.sources.budget import BudgetExhausted, Limits, RequestBudget
from jobcu.sources.http import Blocked, PoliteClient

NOW = datetime.now(UTC)


def term(text, language="en", kind="job_title"):
    return SearchTerm(text=text, language=language, kind=kind)


def context(handler, source_id="test"):
    keys = KeyStore()
    keys.set("adzuna_app_id", "fake-id-123")
    keys.set("adzuna_app_key", "fake-key-1234567890")
    keys.set("reed_api_key", "fake-reed-key-123456")
    http = PoliteClient(min_intervals={}, sleep=lambda s: None,
                        transport=httpx.MockTransport(handler))
    report = SourceReport(source_id, source_id)
    return SourceContext(http, keys, report, lambda: False, lambda message: None)


# --- Adzuna ---------------------------------------------------------------------------


def test_adzuna_combines_single_words_and_puts_field_phrases_first():
    terms = [term("Hardwareentwickler", "de"), term("Leistungselektronik", "de", "field_or_skill"),
             term("Hardware Engineer"), term("power electronics", kind="field_or_skill"),
             term("Ingénieur hardware", "fr")]
    assert adzuna.plan_searches(terms, "DE") == [
        {"what_or": "Hardwareentwickler Leistungselektronik"},
        {"what_phrase": "power electronics"},
        {"what_phrase": "Hardware Engineer"},
    ]


def adzuna_item(job_id, created):
    return {"id": job_id, "title": "Hardware Engineer", "created": created,
            "company": {"display_name": "Acme"}, "location": {"display_name": "Berlin"},
            "redirect_url": f"https://www.adzuna.de/land/ad/{job_id}",
            "contract_type": "permanent", "contract_time": "full_time", "description": "Short"}


def test_adzuna_stops_at_jobs_older_than_the_window():
    fresh = (NOW - timedelta(hours=2)).isoformat()
    old = (NOW - timedelta(days=5)).isoformat()
    pages = []

    def handler(request):
        pages.append(request.url.path)
        results = [adzuna_item(str(i), fresh) for i in range(49)] + [adzuna_item("old", old)]
        return httpx.Response(200, json={"results": results})

    ctx = context(handler, "adzuna")
    query = JobQuery(["DE"], [], [term("Hardwareentwickler", "de")], 24, NOW)
    jobs = list(adzuna.AdzunaSource().search(query, ctx))
    assert len(jobs) == 49 and len(pages) == 1
    assert jobs[0].job_types == ["full_time_permanent"] and jobs[0].date_precision == "exact"
    assert not jobs[0].description_is_complete


def test_adzuna_passes_place_and_distance():
    seen = {}

    def handler(request):
        seen.update(request.url.params)
        return httpx.Response(200, json={"results": []})

    place = Place(name="Munich", local_name="München", country="DE", kind="city", radius_km=50)
    query = JobQuery(["DE"], [place], [term("Hardwareentwickler", "de")], 24, NOW)
    list(adzuna.AdzunaSource().search(query, context(handler, "adzuna")))
    assert seen["where"] == "München" and seen["distance"] == "50"


def test_adzuna_rejected_keys_fail_only_this_source():
    ctx = context(lambda request: httpx.Response(401, json={}), "adzuna")
    query = JobQuery(["GB"], [], [term("Hardware")], 24, NOW)
    with pytest.raises(SourceError, match="didn't accept"):
        list(adzuna.AdzunaSource().search(query, ctx))


# --- Reed -----------------------------------------------------------------------------


def test_reed_keeps_fresh_jobs_and_reads_full_ads_on_request():
    today = NOW.strftime("%d/%m/%Y")
    old = (NOW - timedelta(days=10)).strftime("%d/%m/%Y")

    def handler(request):
        if request.url.path.endswith("/search"):
            return httpx.Response(200, json={"totalResults": 2, "results": [
                {"jobId": 1, "jobTitle": "Electronics Engineer", "employerName": "Acme",
                 "locationName": "Bristol", "date": today, "jobDescription": "Short",
                 "jobUrl": "https://www.reed.co.uk/jobs/1"},
                {"jobId": 2, "jobTitle": "Old job", "employerName": "Acme",
                 "locationName": "Bristol", "date": old, "jobDescription": "Short"},
            ]})
        return httpx.Response(200, json={
            "jobId": 1,
            "datePosted": today,
            "jobDescription": "<p>Full <b>ad</b></p><ul><li>PCB</li></ul>",
            "contractType": "Permanent", "fullTime": True, "partTime": False,
            "externalUrl": "https://careers.acme.example/1", "minimumSalary": 45000,
            "maximumSalary": 55000,
        })

    source = reed.ReedSource()
    ctx = context(handler, "reed")
    query = JobQuery(["GB"], [], [term("Electronics Engineer")], 24, NOW)
    jobs = list(source.search(query, ctx))
    assert [j.source_job_id for j in jobs] == ["1"]
    full = source.load_details(jobs[0], ctx)
    assert full.description_is_complete and "• PCB" in full.description
    assert full.job_types == ["full_time_permanent"]
    assert full.salary_text == "£45,000 – £55,000"
    assert full.employer_url == "https://careers.acme.example/1"


# --- Bundesagentur ----------------------------------------------------------------------


def test_bundesagentur_reads_country_types_and_first_publication_date():
    item = {
        "referenznummer": "10001-1", "stellenangebotsTitel": "Hardwareentwickler (m/w/d)",
        "firma": "Acme GmbH", "stellenangebotsart": "ARBEIT", "vertragsdauer": "BEFRISTET",
        "arbeitszeitVollzeit": True, "datumErsteVeroeffentlichung": NOW.date().isoformat(),
        "stellenlokationen": [{"adresse": {"ort": "Linz", "land": "ÖSTERREICH"},
                               "breite": 48.3, "laenge": 14.3}],
    }

    def handler(request):
        if request.url.path.endswith("/jobs"):
            return httpx.Response(200, json={"ergebnisliste": [item], "maxErgebnisse": 1})
        return httpx.Response(200, json={**item, "stellenangebotsBeschreibung": "Full ad text"})

    source = bundesagentur.BundesagenturSource()
    ctx = context(handler, "bundesagentur")
    query = JobQuery(["DE"], [], [term("Hardwareentwickler", "de")], 24, NOW)
    jobs = list(source.search(query, ctx))
    assert len(jobs) == 1
    assert jobs[0].country == "AT" and jobs[0].job_types == ["fixed_term"]
    assert jobs[0].url.endswith("/jobdetail/10001-1")
    full = source.load_details(jobs[0], ctx)
    assert full.description == "Full ad text" and full.description_is_complete


def test_bundesagentur_changed_interface_is_reported_plainly():
    ctx = context(lambda request: httpx.Response(404, json={}), "bundesagentur")
    query = JobQuery(["DE"], [], [term("Hardwareentwickler", "de")], 24, NOW)
    with pytest.raises(SourceError, match="may have changed"):
        list(bundesagentur.BundesagenturSource().search(query, ctx))


# --- Budgets and polite requests --------------------------------------------------------


def test_daily_request_limit_is_kept():
    budget = RequestBudget("adzuna", "Adzuna", Limits(per_day=2))
    budget.spend()
    budget.spend()
    with pytest.raises(BudgetExhausted, match="today"):
        budget.spend()
    # Another search on the same day is limited too.
    with pytest.raises(BudgetExhausted):
        RequestBudget("adzuna", "Adzuna", Limits(per_day=2)).spend()


def test_polite_client_waits_as_asked_and_remembers_answers():
    calls, sleeps = [], []

    def handler(request):
        calls.append(1)
        if len(calls) == 1:
            return httpx.Response(429, headers={"retry-after": "7"})
        return httpx.Response(200, json={"ok": True})

    http = PoliteClient(min_intervals={}, sleep=sleeps.append,
                        transport=httpx.MockTransport(handler))
    assert http.get("https://example.test/a").json() == {"ok": True}
    assert sleeps[0] == 7.0  # waited as the site asked
    http.get("https://example.test/a")
    assert len(calls) == 2  # the second request came from memory


def test_bot_protection_is_never_worked_around():
    def handler(request):
        return httpx.Response(403, text="<html>Please complete the CAPTCHA</html>")

    http = PoliteClient(min_intervals={}, sleep=lambda s: None,
                        transport=httpx.MockTransport(handler))
    with pytest.raises(Blocked):
        http.get("https://example.test/")
