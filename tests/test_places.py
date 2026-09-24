"""The town list Jobcu ships and the distances it measures."""

from jobcu import places
from jobcu.countries import COUNTRIES
from jobcu.location import Place
from jobcu.sources.matching import matches_places


def test_towns_are_found_by_their_english_and_local_names():
    munich = places.find("Munich", "DE")
    assert munich is not None and munich.country == "DE"
    assert places.find("München", "DE") == munich
    assert places.find("Muenchen", "DE") == munich
    # The biggest town wins when several share a name, and the country narrows it down.
    assert places.find("Cambridge", "GB").country == "GB"
    assert places.find("Dublin", "IE").people > 500_000
    assert places.find("Nowhere at all", "IE") is None
    assert places.find("Munich", "IE") is None


def test_shortened_names_in_job_ads_still_find_the_town():
    assert places.find("Ottobrunn", "DE").name.startswith("Ottobrunn")
    assert places.find("Halle", "DE").name.startswith("Halle")
    assert places.find("Frankfurt", "DE").people > 500_000


def test_locate_reads_the_town_out_of_a_job_location():
    assert places.locate("Ireland, Limerick", "IE").name == "Limerick"
    assert places.locate("Garching bei München, Bayern", "DE").name.startswith("Garching")
    assert places.locate("Frankfurt am Main, Germany", "DE").name == "Frankfurt am Main"
    assert places.locate("Remote", "DE") is None
    # A district or county named after a big town isn't that town (a real Adzuna location).
    assert places.locate("Unterhaching, München (Kreis)", "DE").name == "Unterhaching"
    assert places.locate("Gilching, Starnberg (Kreis)", "DE").name == "Gilching"
    assert places.locate("Ballincollig, Co. Cork", "IE").name == "Ballincollig"
    assert places.locate("München (Kreis)", "DE").name == "Munich"  # nothing more precise
    assert places.locate("Moosach, München", "DE").name == "Munich"  # a part of the city
    assert places.locate("", "DE") is None


def test_states_and_nations_are_never_read_as_a_town():
    # Each of these also names a town: Sachsen bei Ansbach, Brandenburg an der Havel, Schleswig,
    # a village called Wales, Česká.
    for text, country in [("Sachsen", "DE"), ("Sachsen-Anhalt", "DE"), ("Brandenburg", "DE"),
                          ("Schleswig-Holstein", "DE"), ("Sachsen, Deutschland", "DE"),
                          ("Wales", "GB"), ("Česká republika", "CZ")]:
        assert places.locate(text, country) is None, text
    assert places.locate("Dresden, Sachsen", "DE").name == "Dresden"
    assert places.locate("Cardiff, Wales", "GB").name == "Cardiff"
    assert places.locate("Brandenburg an der Havel", "DE").name == "Brandenburg an der Havel"
    assert places.locate("Berlin", "DE").name == "Berlin"  # a city state is a town too


def test_a_district_after_its_town_is_that_town():
    assert places.locate("Wietmarschen-Lohne", "DE").name == "Wietmarschen"  # not Löhne
    assert places.locate("Hamburg-Wandsbek", "DE").name == "Hamburg"
    assert places.locate("Stuttgart-Vaihingen, Baden-Württemberg", "DE").name == "Stuttgart"
    for town in ("Castrop-Rauxel", "Baden-Baden", "Villingen-Schwenningen"):
        assert places.locate(town, "DE").name == town


def test_distances_are_about_right():
    munich = places.find("Munich", "DE")
    garching = places.locate("Garching", "DE")
    berlin = places.find("Berlin", "DE")
    assert 10 < places.distance_km(munich, garching) < 20
    assert 480 < places.distance_km(munich, berlin) < 520
    assert places.distance_km(munich, munich) == 0


def test_nearby_towns_count_as_the_place_someone_asked_for():
    munich = Place(name="Munich", local_name="München", country="DE", kind="city", radius_km=50)
    assert matches_places([munich], "DE", "Garching bei München")
    assert matches_places([munich], "DE", "Fürstenfeldbruck")
    assert not matches_places([munich], "DE", "Ingolstadt")  # 70 km away
    assert not matches_places([munich], "DE", "Berlin, Germany")
    close = Place(name="Munich", local_name="München", country="DE", kind="city", radius_km=5)
    assert not matches_places([close], "DE", "Garching")
    assert matches_places([close], "DE", "München-Schwabing")
    # Without a distance, "around the city" is as wide as the job sites' own filters.
    plain = Place(name="Munich", local_name="München", country="DE", kind="city", radius_km=None)
    assert matches_places([plain], "DE", "Garching")
    assert not matches_places([plain], "DE", "Ingolstadt")
    # A region has no single point, so only its name counts.
    bavaria = Place(name="Bavaria", local_name="Bayern", country="DE", kind="region",
                    radius_km=None)
    assert matches_places([bavaria], "DE", "Ingolstadt, Bayern")
    assert not matches_places([bavaria], "DE", "Hamburg")


def test_the_shipped_list_covers_every_supported_country():
    towns = {town for entries in places._towns().values() for town in entries}
    assert len(towns) > 50_000
    assert {town.country for town in towns} == set(COUNTRIES)


def test_every_town_knows_its_state_and_district():
    radeberg = places.find("Radeberg", "DE")
    assert radeberg.lies_in("DE.13")  # Saxony
    assert radeberg.lies_in("DE.K.14625") and not radeberg.lies_in("DE.K.14612")  # Bautzen
    assert places.find("Clacton-on-Sea", "GB").lies_in(places.find_region("Essex", "GB").code)
    assert places.find("Cork", "IE").lies_in(places.find_region("County Cork", "IE").code)


def test_regions_are_found_by_their_english_local_and_short_names():
    for name in ("Saxony", "Sachsen", "Freistaat Sachsen"):
        assert places.find_region(name, "DE").code == "DE.13"
    for name in ("Landkreis Bautzen", "Bautzen district", "Kreis Bautzen", "Bautzen"):
        assert places.find_region(name, "DE").name == "Landkreis Bautzen"
    # A state wins over a district of the same name, and the country must match.
    assert places.find_region("Brandenburg", "DE").level == "region"
    assert places.find_region("Wales", "GB").level == "region"
    assert places.find_region("Saxony", "GB") is None
    assert places.find_region("Atlantis", "DE") is None
