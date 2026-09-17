from jobcu.countries import COUNTRIES, languages_for
from jobcu.keywords import SearchTerm, tidy_terms
from jobcu.location import LocationUnderstanding, Place, interpret_location, plan_from


def understanding(**changes):
    base = {
        "understood_as": "Jobs in Munich.",
        "limits_countries": True,
        "countries": [],
        "places": [],
        "not_checked_yet": [],
        "outside_supported_area": [],
    }
    return LocationUnderstanding.model_validate({**base, **changes})


def test_supported_countries_are_the_owners_30():
    from jobcu.countries import LANGUAGE_NAMES

    assert len(COUNTRIES) == 30
    assert {"IE", "GB", "DE", "PL", "PT", "RO", "GR", "HU", "HR", "SK", "EE", "LV", "LT"} <= set(
        COUNTRIES
    )
    assert not {"LI", "SM", "AD", "MC", "VA", "TR", "RU", "UA", "BG"} & set(COUNTRIES)
    assert all(lang in LANGUAGE_NAMES for c in COUNTRIES.values() for lang in c.ad_languages)


def test_named_places_limit_languages_to_what_is_spoken_there():
    zurich = Place(name="Zurich", local_name="Zürich", country="CH", kind="city",
                   radius_km=None, languages=["de"])
    assert languages_for(["CH"], [zurich]) == ["en", "de"]
    assert languages_for(["CH"]) == ["en", "de", "fr", "it"]
    # A language the country doesn't use for job ads is ignored, falling back to the country's.
    odd = Place(name="Geneva", local_name="Genève", country="CH", kind="city",
                radius_km=None, languages=["pl"])
    assert languages_for(["CH"], [odd]) == ["en", "de", "fr", "it"]
    assert languages_for(["IE", "DE"], [zurich]) == ["en", "de"]


def test_languages_start_with_english_without_repeats():
    assert languages_for(["DE", "AT", "CH", "IE"]) == ["en", "de", "fr", "it"]


def test_empty_location_searches_everywhere_without_asking_the_ai():
    class NoAI:
        def generate(self, *args, **kwargs):
            raise AssertionError("the AI should not be asked")

    plan = interpret_location(NoAI(), "   ")
    assert plan.broad and len(plan.countries) == len(COUNTRIES)


def test_named_place_adds_its_country():
    place = Place(name="Munich", local_name="München", country="DE", kind="city", radius_km=50)
    plan = plan_from("Munich", understanding(places=[place]))
    assert plan.countries == ["DE"] and not plan.broad


def test_unlimited_description_searches_everywhere_and_keeps_notes():
    plan = plan_from(
        "a city by the sea",
        understanding(limits_countries=False, not_checked_yet=["city by the sea"]),
    )
    assert plan.broad and plan.not_checked_yet == ["city by the sea"]


def test_places_outside_the_supported_area_are_reported():
    plan = plan_from("Tokyo", understanding(outside_supported_area=["Tokyo"], countries=[]))
    assert plan.broad and plan.outside_supported_area == ["Tokyo"]


def test_search_words_are_tidied():
    terms = [
        SearchTerm(text="Hardware  Engineer", language="en", kind="job_title"),
        SearchTerm(text="hardware engineer", language="en", kind="job_title"),
        SearchTerm(text="Leistungselektronik", language="de", kind="field_or_skill"),
        SearchTerm(text="Hardwareentwickler", language="de", kind="job_title"),
        SearchTerm(text="Ingénieur", language="fr", kind="job_title"),
    ]
    tidy = tidy_terms(terms, ["en", "de"])
    assert [(t.language, t.text) for t in tidy] == [
        ("en", "Hardware Engineer"),
        ("de", "Hardwareentwickler"),
        ("de", "Leistungselektronik"),
    ]


def test_search_words_per_language_are_capped():
    terms = [SearchTerm(text=f"Title {i}", language="en", kind="job_title") for i in range(40)]
    assert len(tidy_terms(terms, ["en"])) == 16
