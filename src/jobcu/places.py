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
REGIONS = Path(__file__).resolve().parent / "data" / "regions.csv.gz"
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

# States, nations and provinces a location may name on its own ("Sachsen", "Wales"). Some share a
# name with a town ("Sachsen bei Ansbach", Brandenburg an der Havel, a village called Wales), so
# they never count as that town: a job in "Sachsen" could be anywhere in Saxony. City states
# (Berlin, Hamburg, Bremen) and Salzburg are towns as well and aren't listed.
_REGIONS = frozenset(normalise(name) for name in (
    "Baden-Württemberg", "Bayern", "Bavaria", "Brandenburg", "Hessen", "Hesse",
    "Mecklenburg-Vorpommern", "Niedersachsen", "Lower Saxony", "Nordrhein-Westfalen",
    "North Rhine-Westphalia", "NRW", "Rheinland-Pfalz", "Rhineland-Palatinate", "Saarland",
    "Sachsen", "Saxony", "Sachsen-Anhalt", "Saxony-Anhalt", "Schleswig-Holstein", "Thüringen",
    "Thuringia", "England", "Scotland", "Wales", "Cymru", "Northern Ireland", "Great Britain",
    "United Kingdom", "Leinster", "Munster", "Connacht", "Ulster", "Tirol", "Tyrol",
    "Vorarlberg", "Kärnten", "Carinthia", "Steiermark", "Styria", "Niederösterreich",
    "Oberösterreich", "Burgenland", "Česká republika", "Česko", "Czechia", "Czech Republic",
))


@dataclass(frozen=True)
class Town:
    name: str
    country: str
    latitude: float
    longitude: float
    people: int
    # The state, province or nation, and the county or district, as codes in `regions.csv.gz`
    # ("DE.13" is Saxony, "DE.K.14625" Landkreis Bautzen).
    region: str = ""
    district: str = ""

    def lies_in(self, code: str) -> bool:
        return code in (self.region, self.district)


@dataclass(frozen=True)
class Region:
    code: str
    level: str  # "region" (a state, province or nation) or "district" (a county or district)
    country: str
    name: str


@cache
def _towns(path: Path = DATA) -> dict[str, tuple[Town, ...]]:
    """Every town by its normalised name, biggest first ("Berlin" is the German capital)."""
    index: dict[str, list[Town]] = {}
    with gzip.open(path, "rt", encoding="utf-8") as file:
        for row in csv.reader(line for line in file if not line.startswith("#")):
            names, country, latitude, longitude, people, *codes = row
            spellings = names.split("|")
            town = Town(spellings[0], country, float(latitude), float(longitude), int(people),
                        *codes)
            written = {normalise(name) for name in spellings}
            short = {normalise(_QUALIFIERS.sub("", name)) for name in spellings}
            for spelling in (written | short) - {""}:
                index.setdefault(spelling, []).append(town)
    return {name: tuple(sorted(towns, key=lambda t: -t.people))
            for name, towns in index.items()}


@cache
def towns_in(country: str) -> tuple[Town, ...]:
    """Every town of one country in the list, biggest first."""
    unique = {town for towns in _towns().values() for town in towns if town.country == country}
    return tuple(sorted(unique, key=lambda town: -town.people))


# Words that say what kind of region a name is, not which one: "Landkreis Bautzen", "Bautzen
# district" and "Bautzen" are the same district; "Free State of Saxony" is Saxony.
_REGION_WORDS = re.compile(
    r"\b(?:landkreis|kreisfreie stadt|stadtkreis|kreis|bezirk|regierungsbezirk|district|"
    r"county|borough|royal borough|city and county|city|metropolitan|unitary authority|council|"
    r"region|province|provincia|provincie|state|free state|freistaat|land|bundesland|"
    r"department|departement|département|voivodeship|województwo|of|the|de|di|del|du|la|le)\b"
)


def _region_key(name: str | None) -> str:
    return " ".join(_REGION_WORDS.sub(" ", normalise(name)).split())


@cache
def _regions(path: Path = REGIONS) -> dict[str, tuple[Region, ...]]:
    """Every state, province, nation, county and district by its normalised names, with and
    without words like "Landkreis" or "County"."""
    index: dict[str, list[Region]] = {}
    with gzip.open(path, "rt", encoding="utf-8") as file:
        for row in csv.reader(line for line in file if not line.startswith("#")):
            code, level, country, names = row
            spellings = names.split("|")
            region = Region(code, level, country, spellings[0])
            keys = {normalise(name) for name in spellings} | {_region_key(n) for n in spellings}
            for key in keys - {""}:
                index.setdefault(key, []).append(region)
    return {key: tuple(regions) for key, regions in index.items()}


def find_region(name: str | None, country: str | None = None) -> Region | None:
    """The state, province, nation, county or district with this name, in the given country.
    A whole name wins over a shortened one, and a state over a district of the same name."""
    for key in (normalise(name), _region_key(name)):
        found = [region for region in _regions().get(key, ())
                 if country is None or region.country == country]
        if found:
            return min(found, key=lambda region: region.level != "region")
    return None


@cache
def _regions_by_code() -> dict[str, Region]:
    return {region.code: region for regions in _regions().values() for region in regions}


def region_name(code: str) -> str:
    region = _regions_by_code().get(code)
    return region.name if region else code


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
    Unterhaching), and a state or nation never counts ("Sachsen" is no town).
    """
    parts = [_town_of_district(part) for part in re.split(r"[,;|]", text or "")
             if normalise(part) not in _REGIONS]
    if not any(part.strip() for part in parts):
        return None
    text = ", ".join(parts)
    precise = [part for part in parts if not _DISTRICT.search(part)]
    if precise and len(precise) < len(parts):
        town = _locate(", ".join(precise), country)
        if town is not None:
            return town
    return _locate(text, country)


_HYPHENATED = re.compile(r"\b(\w+)-(\w+(?:-\w+)*)\b")


def _town_of_district(text: str) -> str:
    """Ads write a district after its town: "Wietmarschen-Lohne" is Lohne in Wietmarschen, not
    the town of Löhne. A hyphenated name the list doesn't know stands for its first part, when
    that is a town ("Castrop-Rauxel" is a town in its own right and stays)."""
    def first_part(match: re.Match) -> str:
        whole, town = match.group(0), match.group(1)
        return town if find(whole) is None and find(town) is not None else whole

    return _HYPHENATED.sub(first_part, text)


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
    return km(a.latitude, a.longitude, b.latitude, b.longitude)


def km(lat_a: float, lon_a: float, lat_b: float, lon_b: float) -> float:
    """Distance in a straight line between two points on the map."""
    lat1, lon1, lat2, lon2 = map(radians, (lat_a, lon_a, lat_b, lon_b))
    haversine = sin((lat2 - lat1) / 2) ** 2 + cos(lat1) * cos(lat2) * sin((lon2 - lon1) / 2) ** 2
    return 2 * EARTH_RADIUS_KM * asin(sqrt(haversine))
