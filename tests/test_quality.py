"""The score check: ads kept from real searches and what the person thinks of them."""

import pytest
from fastapi.testclient import TestClient

from jobcu import quality
from jobcu.app import create_app

HEADERS = {"X-Jobcu": "1"}


@pytest.fixture
def client():
    return TestClient(create_app(), base_url="http://127.0.0.1:8765")


def ad(job_id, score=None, title="Hardware Engineer", text="The whole ad"):
    return {"source": "greenhouse", "source_job_id": job_id, "title": title,
            "company": "Fake Devices", "location": "Dublin, Ireland",
            "url": f"https://example.test/{job_id}", "score": score, "text": text}


def test_a_search_keeps_a_spread_of_its_jobs_and_left_out_titles():
    scored = [ad(str(i), score=score) for i, score in enumerate([95, 88, 70, 65, 55, 50, 30, 20])]
    titles = [ad(f"t{i}", title="Servicetechniker") for i in range(3)]
    added = quality.collect_from_search(scored, titles)
    assert added == {"scored": 8, "title_only": 3}
    kept = quality.all_ads()
    assert {a.score for a in kept if a.kind == "scored"} == {95, 88, 70, 65, 55, 50, 30, 20}
    assert quality.progress()["scored"] == {"wanted": 40, "collected": 8, "rated": 0}

    # The same jobs in the next search aren't kept twice.
    assert quality.collect_from_search(scored, titles) == {"scored": 0, "title_only": 0}


def test_only_a_few_jobs_per_search_and_never_more_than_wanted():
    many = [ad(str(i), score=i) for i in range(100)]
    assert quality.collect_from_search(many, [])["scored"] == quality.PER_SEARCH["scored"]
    # Jobs are taken from every part of the score range, not just the top.
    scores = sorted(a.score for a in quality.all_ads())
    assert scores[0] < 40 and scores[-1] > 74


def test_rating_an_ad_and_taking_it_back(client):
    quality.collect_from_search([ad("1", score=80)], [ad("t1", title="Cleaner")])
    data = client.get("/api/quality", headers=HEADERS).json()
    scored_ad = next(a for a in data["ads"] if a["kind"] == "scored")
    assert scored_ad["rating"] is None and scored_ad["score"] == 80
    assert {b["id"] for b in data["blockers"]} == set(quality.BLOCKERS)

    answer = client.put(f"/api/quality/{scored_ad['id']}", headers=HEADERS,
                        json={"rating": "poor", "blockers": ["language", "nonsense"],
                              "note": "German C1"}).json()
    assert answer["ad"]["rating"] == "poor" and answer["ad"]["blockers"] == ["language"]
    assert answer["ad"]["rated_by"] == "owner" and answer["progress"]["scored"]["rated"] == 1

    answer = client.put(f"/api/quality/{scored_ad['id']}", headers=HEADERS,
                        json={"rating": None, "blockers": [], "note": ""}).json()
    assert answer["ad"]["rating"] is None and answer["progress"]["scored"]["rated"] == 0


def test_titles_have_their_own_answers(client):
    quality.collect_from_search([], [ad("t1", title="Cleaner")])
    title_ad = next(a for a in client.get("/api/quality", headers=HEADERS).json()["ads"]
                    if a["kind"] == "title_only")
    ok = client.put(f"/api/quality/{title_ad['id']}", headers=HEADERS,
                    json={"rating": "worth_a_look"})
    assert ok.json()["ad"]["rating"] == "worth_a_look"
    # A rating from the wrong list is refused, as is an unknown job.
    assert client.put(f"/api/quality/{title_ad['id']}", headers=HEADERS,
                      json={"rating": "good"}).status_code == 400
    assert client.put("/api/quality/999", headers=HEADERS,
                      json={"rating": "good"}).status_code == 404
