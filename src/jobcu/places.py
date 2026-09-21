"""Towns and how far apart they are, so "within 50 km" works for sources that give only a name.

Job sources with their own location filter (Adzuna, Reed, the Bundesagentur) do the distance
work themselves. Company career sites and some job boards only say "Garching" or "Ireland,
Limerick", so Jobcu looks the town up in the list it ships (`data/places.csv.gz`, from GeoNames)
and measures the distance itself.

The list holds every town with at least 1,000 inhabitants in the supported countries, so small
villages and company sites are missed; those jobs are kept only when their text names the place
(see `sources/matching.py`).
"""

import csv
import gzip
import re
from dataclasses import dataclass
from functools import cache
from math import asin, cos, radians, sin, sqrt
from pathlib import Path

from jobcu.text import normalise

DATA = Path(__file__).resolve().parent / "data" / "places.csv.gz"
MAX_NAME_WORDS = 4  # "Frankfurt am Main", "'s-Hertogenbosch"
EARTH_RADIUS_KM = 6371.0
# Job ads shorten names: "Ottobrunn" for "Ottobrunn bei München", "Halle" for "Halle (Saale)".
_QUALIFIERS = re.compile(
    r"\s*[(,].*|\s+(?:bei|an der|an dem|am|im|in der|ob der|vor der|unter|auf|a\.d\.|sur|sous|"
    r"près de|nad|nad|pri|del|di|de|na)\s+.*$",
    re.IGNORECASE,
)
# Parts of a location that name a district or county, not a town: "München (Kreis)" is the
# district around Munich, not the city, and "Co. Cork" is the county, not Cork city. They are
# used only when nothing more precise is named.
_DISTRICT = re.compile(
    r"\((?:land)?kreis\)|\b(?:land)?kreis\b|\bco\.?\s|\bcounty\b|\bbezirk\b|\bdistrict\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Town:
    name: str
    country: str
    latitude: float
    longitude: float
    people: int


@cache
def _towns(path: Path = DATA) -> dict[str, tuple[Town, ...]]:
    """Every town by its normalised name, biggest first ("Berlin" is the German capital)."""
    index: dict[str, list[Town]] = {}
    with gzip.open(path, "rt", encoding="utf-8") as file:
        for row in csv.reader(line for line in file if not line.startswith("#")):
            names, country, latitude, longitude, people = row
            spellings = names.split("|")
            town = Town(spellings[0], country, float(latitude), float(longitude), int(people))
            written = {normalise(name) for name in spellings}
            short = {normalise(_QUALIFIERS.sub("", name)) for name in spellings}
            for spelling in (written | short) - {""}:
                index.setdefault(spelling, []).append(town)
    return {name: tuple(sorted(towns, key=lambda t: -t.people))
            for name, towns in index.items()}


def find(name: str | None, country: str | None = None) -> Town | None:
    """The best known town with this name, preferring the one in the given country."""
    towns = _towns().get(normalise(name))
    if not towns:
        return None
    if country:
        in_country = [town for town in towns if town.country == country]
        return in_country[0] if in_country else None
    return towns[0]


def locate(text: str | None, country: str | None = None) -> Town | None:
    """The town a free-text location names ("Ireland, Limerick" → Limerick).

    Longer names win ("Frankfurt am Main" over "Frankfurt"), then the bigger town. A district
    or county counts only when no town is named besides it ("Unterhaching, München (Kreis)" is
    Unterhaching).
    """
    parts = re.split(r"[,;|]", text or "")
    precise = [part for part in parts if not _DISTRICT.search(part)]
    if precise and len(precise) < len(parts):
        town = _locate(", ".join(precise), country)
        if town is not None:
            return town
    return _locate(text, country)


def _locate(text: str | None, country: str | None) -> Town | None:
    words = normalise(text).split()
    best: Town | None = None
    best_words = 0
    for start in range(len(words)):
        for length in range(min(MAX_NAME_WORDS, len(words) - start), 0, -1):
            if length < best_words:
                break
            town = find(" ".join(words[start : start + length]), country)
            if town is not None and (length > best_words or
                                     (best is not None and town.people > best.people)):
                best, best_words = town, length
    return best


def distance_km(a: Town, b: Town) -> float:
    """Distance in a straight line, which is close enough for "within 50 km"."""
    lat1, lon1, lat2, lon2 = map(radians, (a.latitude, a.longitude, b.latitude, b.longitude))
    haversine = sin((lat2 - lat1) / 2) ** 2 + cos(lat1) * cos(lat2) * sin((lon2 - lon1) / 2) ** 2
    return 2 * EARTH_RADIUS_KM * asin(sqrt(haversine))
