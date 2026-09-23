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


def test_adzuna_asks_for_titles_in_the_title_first_then_specialist_words_anywhere():
    terms = [term("Hardware Engineer"), term("Hardware Design Engineer"),
             term("Embedded Hardware Engineer"), term("PCB Design Engineer"),
             term("Hardwareentwickler", "de"), term("Hardware Engineer", "de"),
             term("Leistungselektronik", "de", "field_or_skill"),
             term("Schaltungsentwicklung", "de", "field_or_skill"),
             term("power electronics", kind="field_or_skill"),
             term("Power Electronics", "de", "field_or_skill"), term("Ingénieur hardware", "fr")]
    assert adzuna.plan_searches(terms, "DE") == [
        # "Hardware Design Engineer" and "Embedded Hardware Engineer" are found by the first.
        {"title_only": "Hardware Engineer"},
        {"title_only": "PCB Design Engineer"},
        {"title_only": "Hardwareentwickler"},
        {"what_or": "Leistungselektronik Schaltungsentwicklung"},
        {"what_phrase": "power electronics"},
    ]


def adzuna_item(job_id, created):
    return {"id": job_id, "title": "Hardware Engineer", "created": created,
            "company": {"display_name": "Acme"}, "location": {"display_name": "Berlin"},
            "redirect_url": f"https://www.adzuna.de/land/ad/{job_id}",
            "contract_type": "permanent", "contract_time": "full_time", "description": "Short"}


def test_adzuna_reads_by_relevance_and_keeps_only_jobs_inside_the_window():
    fresh = (NOW - timedelta(hours=2)).isoformat()
    old = (NOW - timedelta(hours=30)).isoformat()  # inside Adzuna's whole days, outside 24 h
    requests = []

    def handler(request):
        requests.append(dict(request.url.params))
        page = int(request.url.path.rsplit("/", 1)[1])
        if page == 1:
            results = [adzuna_item("old", old)] + [adzuna_item(str(i), fresh) for i in range(49)]
        else:
            results = [adzuna_item(f"p2-{i}", fresh) for i in range(10)]
        return httpx.Response(200, json={"count": 60, "results": results})

    ctx = context(handler, "adzuna")
    query = JobQuery(["DE"], [], [term("Hardwareentwickler", "de")], 24, NOW)
    jobs = list(adzuna.AdzunaSource().search(query, ctx))
    assert len(jobs) == 59 and len(requests) == 2
    assert requests[0]["sort_by"] == "relevance"
    assert requests[0]["title_only"] == "Hardwareentwickler"
    assert jobs[0].job_types == ["full_time_permanent"] and jobs[0].date_precision == "exact"
    assert not jobs[0].description_is_complete


def test_a_broad_adzuna_search_gets_a_fair_part_and_can_t_crowd_out_the_rest(monkeypatch):
    monkeypatch.setattr(adzuna, "share_of_month",
                        lambda source, limits: Limits(per_search=6, per_day=240, per_month=2400))
    fresh = (NOW - timedelta(hours=2)).isoformat()
    asked = []

    def handler(request):  # every search matches endless ads
        params = dict(request.url.params)
        asked.append("title" if "title_only" in params else "phrase")
        return httpx.Response(200, json={"count": 5000, "results": [
            adzuna_item(f"{len(asked)}-{i}", fresh) for i in range(50)]})

    query = JobQuery(["DE"], [], [term("Hardwareentwickler", "de"),
                                  term("power electronics", kind="field_or_skill")], 24, NOW)
    list(adzuna.AdzunaSource().search(query, context(handler, "adzuna")))
    assert asked == ["title"] * 3 + ["phrase"] * 3


def test_what_one_country_doesn_t_need_goes_to_the_next(monkeypatch):
    monkeypatch.setattr(adzuna, "share_of_month",
                        lambda source, limits: Limits(per_search=8, per_day=240, per_month=2400))
    fresh = (NOW - timedelta(hours=2)).isoformat()
    asked = []

    def handler(request):  # Germany has three ads; the UK has endless ones
        country = request.url.path.split("/")[-3]
        asked.append(country)
        count = 3 if country == "de" else 50
        return httpx.Response(200, json={"results": [
            adzuna_item(f"{len(asked)}-{i}", fresh) for i in range(count)]})

    query = JobQuery(["DE", "GB"], [], [term("Hardware Engineer")], 24, NOW)
    list(adzuna.AdzunaSource().search(query, context(handler, "adzuna")))
    assert asked == ["de"] + ["gb"] * 7


def test_adzuna_passes_place_and_distance():
    seen = {}

    def handler(request):
        seen.update(request.url.params)
        return httpx.Response(200, json={"results": []})

    place = Place(name="Munich", local_name="München", country="DE", kind="city", radius_km=50)
    query = JobQuery(["DE"], [place], [term("Hardwareentwickler", "de")], 24, NOW)
    list(adzuna.AdzunaSource().search(query, context(handler, "adzuna")))
    assert seen["where"] == "München" and seen["distance"] == "50"


def test_one_failing_adzuna_search_leaves_the_others_running():
    fresh = (NOW - timedelta(hours=2)).isoformat()
    asked = []

    def handler(request):
        params = dict(request.url.params)
        asked.append(params.get("title_only") or params.get("what_phrase"))
        if params.get("title_only") == "Hardware Engineer":
            return httpx.Response(503, json={})  # what Adzuna answered on 2026-09-23
        return httpx.Response(200, json={"results": [adzuna_item(str(len(asked)), fresh)]})

    ctx = context(handler, "adzuna")
    query = JobQuery(["DE"], [], [term("Hardware Engineer"), term("Hardwareentwickler", "de"),
                                  term("power electronics", kind="field_or_skill")], 24, NOW)
    jobs = list(adzuna.AdzunaSource().search(query, ctx))
    # The failing one is retried politely first, then the others are asked for as usual.
    assert list(dict.fromkeys(asked)) == ["Hardware Engineer", "Hardwareentwickler",
                                          "power electronics"]
    assert len(jobs) == 2 and ctx.report.status == "partial"
    assert "code 503" in ctx.report.message


def test_adzuna_gives_up_when_every_search_fails():
    ctx = context(lambda request: httpx.Response(503, json={}), "adzuna")
    terms = [term(f"Title {i}") for i in range(5)]
    with pytest.raises(SourceError, match="code 503"):
        list(adzuna.AdzunaSource().search(JobQuery(["DE"], [], terms, 24, NOW), ctx))


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


# --- Sharing a free monthly allowance -------------------------------------------------


def test_adzuna_budget_shares_what_is_left_of_the_month():
    from datetime import datetime

    from jobcu import db
    from jobcu.sources.budget import Limits, share_of_month

    limits = Limits(per_day=240, per_month=2400)

    def on(day: str, used_this_month: int = 0, used_today: int = 0) -> int:
        with db.connect() as conn:
            conn.execute("DELETE FROM source_requests")
            if used_this_month:
                conn.execute(
                    "INSERT INTO source_requests (day, source, count) VALUES (?, 'adzuna', ?)",
                    (day[:8] + "01", used_this_month - used_today),
                )
            if used_today:
                conn.execute(
                    "INSERT INTO source_requests (day, source, count) VALUES (?, 'adzuna', ?)",
                    (day, used_today),
                )
        when = datetime.fromisoformat(day + "T12:00:00+00:00")
        return share_of_month("adzuna", limits, now=lambda: when).per_search

    # 2,400 requests over 31 days at about 3 searches a day is around 25 per search.
    assert on("2026-09-01") == 26
    # Nothing used by the middle of the month: more per search, but never more than 60.
    assert on("2026-09-20", used_this_month=200) == 60
    # Almost everything used: down to the smallest useful number, not zero.
    assert on("2026-09-20", used_this_month=2350) == 25
    # Never more than today's own allowance has left.
    assert on("2026-09-20", used_this_month=1000, used_today=230) == 10
    assert on("2026-09-20", used_this_month=1000, used_today=240) == 0


def test_adzuna_salary_shows_the_currency_and_a_single_figure_once():
    item = {**adzuna_item("1", NOW.isoformat()), "salary_min": 75000, "salary_max": 75000,
            "salary_is_predicted": "0"}
    assert adzuna.to_found_job(item, "GB").salary_text == "£75,000"
    item = {**item, "salary_max": 90000.4}
    assert adzuna.to_found_job(item, "DE").salary_text == "€75,000 – €90,000"
    assert adzuna.to_found_job({**item, "salary_is_predicted": "1"}, "DE").salary_text is None
