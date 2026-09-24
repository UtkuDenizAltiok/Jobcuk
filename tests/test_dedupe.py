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


def test_a_postcode_or_a_district_is_the_same_place_as_its_town():
    # Search 9: Reed's "BB113BP" and Adzuna's "Burnley, Lancashire" were shown as two jobs, and
    # so were "Heeley, Sheffield" and "Sheffield".
    def uk(source, job_id, city):
        return FoundJob(source=source, source_job_id=job_id, url=f"https://{source}/{job_id}",
                        title="Electronics Design Engineer", company="Corriculo Ltd",
                        location_text=city, country="GB")

    kinds = {"adzuna": "aggregator", "reed": "job_board"}
    for a, b in (("BB113BP", "Burnley, Lancashire"), ("Heeley, Sheffield", "Sheffield")):
        assert len(group_duplicates([uk("reed", "1", a), uk("adzuna", "2", b)], kinds)) == 1, a
    assert len(group_duplicates([uk("reed", "1", "BB113BP"), uk("adzuna", "2", "Leeds")],
                                kinds)) == 2


def test_a_career_sites_label_in_brackets_is_not_part_of_the_company():
    # Search 9: the directory's "Rolls-Royce (professional)" never merged with "Rolls-Royce plc".
    assert normal_company("Rolls-Royce (professional)") == normal_company("Rolls-Royce plc")
    assert normal_company("Acme (UK) Ltd") == normal_company("ACME Ltd")


def test_two_summaries_of_one_agency_ad_merge_only_when_nearly_word_for_word_the_same():
    # Search 9: AMF's ad in Castleford came twice from Adzuna, both summaries, both scored 87.
    summary = ("Our client, a manufacturer of power supplies, is looking for an electronics "
               "design engineer to join its growing team in Castleford. You will design analogue "
               "and power circuits, lay out boards and test prototypes in the lab, working "
               "closely with production and quality. A degree in electronic engineering and "
               "some hands-on design experience are needed; training is given.")
    a = job(job_id="1", company="AMF Recruitment", description=summary)
    b = job(job_id="2", company="AMF Recruitment", description=summary + " Apply today.")
    assert len(group_duplicates([a, b], KINDS)) == 1
    # Different clients' summaries of a similar role stay apart, and so do very short ones.
    other = summary.replace("power supplies", "medical lasers").replace("Castleford", "Leeds") \
        .replace("analogue and power circuits", "laser driver boards")
    c = job(job_id="3", company="AMF Recruitment", description=other)
    assert len(group_duplicates([a, c], KINDS)) == 2
    short = [job(job_id=n, company="AMF Recruitment", description="Electronics engineer wanted.")
             for n in ("4", "5")]
    assert len(group_duplicates(short, KINDS)) == 2
