from datetime import UTC, datetime

from jobcu.dedupe import group_duplicates, normal_company, normal_title, title_similarity
from jobcu.sources.base import FoundJob

KINDS = {"adzuna": "aggregator", "board": "job_board"}
TEXT = "We design power electronics for electric cars and need an engineer. " * 20


def job(source="adzuna", job_id="1", title="Hardware Engineer (m/w/d)", company="Acme GmbH",
        city="München", **extra):
    return FoundJob(source=source, source_job_id=job_id, url=f"https://{source}/{job_id}",
                    title=title, company=company, location_text=city, country="DE", **extra)


def test_names_are_normalised():
    assert normal_company("ACME Deutschland GmbH & Co. KG") == "acme"
    assert normal_title("Hardwareentwickler (m/w/d)") == normal_title("Hardwareentwickler (w/m/d)")


def test_titles_at_different_levels_or_with_different_words_differ():
    assert title_similarity("lead electronics engineer", "electronics engineer") == 0
    assert title_similarity("entwicklungsingenieur elektronik",
                            "entwicklungsingenieur elektrotechnik") == 0
    assert title_similarity("verification engineer 586971", "verification engineer 586969") == 0
    assert title_similarity("electrical design engineer", "electrical desig engineer") >= 90


def test_the_same_job_on_two_sources_becomes_one_card_with_the_best_link():
    groups = group_duplicates(
        [job("adzuna", "1", city="Munich"), job("board", "9", company="ACME GmbH")], KINDS
    )
    assert len(groups) == 1
    assert groups[0].main.source == "board"  # job boards rank above aggregators


def test_same_title_in_far_apart_places_stays_separate():
    a = job(job_id="1", latitude=48.14, longitude=11.58)
    b = job(job_id="2", city="Hamburg", latitude=53.55, longitude=9.99)
    assert len(group_duplicates([a, b], KINDS)) == 2


def test_agency_ads_need_matching_text_to_merge():
    a = job(job_id="1", company="Ferchau GmbH")
    b = job(job_id="2", company="Ferchau GmbH")
    assert len(group_duplicates([a, b], KINDS)) == 2
    a.description = b.description = TEXT
    a.description_is_complete = b.description_is_complete = True
    assert len(group_duplicates([a, b], KINDS)) == 1


def test_earliest_date_of_all_copies_counts():
    old = datetime(2026, 9, 1, tzinfo=UTC)
    new = datetime(2026, 9, 16, tzinfo=UTC)
    groups = group_duplicates([
        job("adzuna", "1", posted_at=new, date_precision="exact"),
        job("board", "2", posted_at=old, date_precision="day"),
    ], KINDS)
    assert groups[0].posted_at == old and groups[0].date_precision == "day"


def test_agency_repeat_of_an_employer_ad_is_flagged_not_merged():
    employer = job("board", "1", title="Power Electronics Engineer", company="Acme GmbH",
                   description=TEXT, description_is_complete=True)
    agency = job("board", "2", title="Power Electronics Engineer", company="Brunel GmbH",
                 description=TEXT, description_is_complete=True)
    groups = group_duplicates([employer, agency], KINDS)
    assert len(groups) == 2
    flagged = [g for g in groups if g.possible_duplicate_of is not None]
    assert len(flagged) == 1 and flagged[0].main.company == "Brunel GmbH"


def test_a_country_or_region_alone_never_stops_a_match():
    # Search 8: most Adzuna ads say only "Deutschland"; the same job on another site gives its
    # town and full ad, but "Deutschland" had counted as a town, so almost none merged.
    kinds = {"adzuna": "aggregator", "board": "job_board"}
    for place in ("Deutschland", "Sachsen", ""):
        groups = group_duplicates([job("adzuna", "1", city=place),
                                   job("board", "9", city="Radeberg")], kinds)
        assert len(groups) == 1, place
    # Two towns still keep two jobs apart, big cities included.
    groups = group_duplicates([job("adzuna", "1", city="Munich"), job("board", "9", city="Berlin")],
                              kinds)
    assert len(groups) == 2
