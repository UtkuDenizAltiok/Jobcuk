"""Matching jobs to the search words and named places on Jobcu's side.

Most sources search by words and places themselves. Some can only list their newest jobs
(JobsIreland.ie, company career systems), so Jobcu reads that list and keeps the jobs that
match here. Matching is generous on purpose: the quick relevance check and scoring decide
what's really relevant, so a job is only left out when nothing in it matches.
"""

import re
from collections.abc import Iterable

from jobcu import places as place_list
from jobcu.keywords import SearchTerm
from jobcu.location import Place
from jobcu.text import normalise

# Words this short must match a whole word ("IT" shouldn't match "digital").
_SHORT_WORD = 3
# How far around a named city counts as that city when the person didn't give a distance.
# The job sites that filter by place themselves use about the same.
DEFAULT_RADIUS_KM = 25


def _contains(haystack: str, word: str) -> bool:
    if len(word) <= _SHORT_WORD:
        return re.search(rf"\b{re.escape(word)}\b", haystack) is not None
    return word in haystack


def term_matches(term_text: str, text: str) -> bool:
    """Every word of the term appears in the text, in any order ("Engineer, Hardware" matches
    "Hardware Engineer"; "Elektronik" matches "Leistungselektronik")."""
    words = normalise(term_text).split()
    haystack = normalise(text)
    return bool(words) and all(_contains(haystack, word) for word in words)


def matches_terms(
    terms: Iterable[SearchTerm], languages: set[str], title: str, description: str = ""
) -> bool:
    """Job titles are matched against the title; field words also against the ad text."""
    for term in terms:
        if term.language not in languages:
            continue
        if term_matches(term.text, title):
            return True
        if description and term.kind == "field_or_skill" and term_matches(term.text, description):
            return True
    return False


def matches_places(places: list[Place], country: str, location_text: str | None) -> bool:
    """True when no place was named in this country, or the job is at or near one of them.

    A job's location often names the place itself ("Swords, Co. Dublin"). When it doesn't,
    Jobcu looks the town up in the list it ships and measures the distance, so "Munich or
    within 50 km" also finds a job in Garching. Towns too small to be in the list, and jobs
    whose location says nothing, are kept.
    """
    wanted = [p for p in places if p.country == country]
    if not wanted:
        return True
    location = normalise(location_text)
    if not location:
        return True  # unknown location: can't be proven to be elsewhere
    for place in wanted:
        for name in {place.name, place.local_name}:
            if normalise(name) and _contains(location, normalise(name)):
                return True
    job_town = place_list.locate(location_text, country)
    if job_town is None:
        return False
    for place in wanted:
        if place.kind != "city":
            continue  # a region has no single point to measure from
        town = (place_list.find(place.local_name, country)
                or place_list.find(place.name, country))
        if town is None:
            continue
        if place_list.distance_km(town, job_town) <= (place.radius_km or DEFAULT_RADIUS_KM):
            return True
    return False
