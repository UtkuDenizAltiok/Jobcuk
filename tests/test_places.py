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
    assert places.locate("", "DE") is None


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
