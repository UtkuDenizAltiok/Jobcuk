"""Rebuilds the list of towns Jobcu ships (src/jobcu/data/places.csv.gz) and the regions they
lie in (src/jobcu/data/regions.csv.gz).

Jobcu needs coordinates for towns so it can tell how far a job is from the place someone asked
for, when a job source gives only a place name, and the region of each town so a fact decided for
a whole state or district ("far-right parties are strong everywhere in Saxony") applies to its
small towns too. The lists come from GeoNames' free exports, narrowed to the supported countries:

- `cities1000`: every place with at least 1,000 inhabitants, with its coordinates and region
  codes (10 MB).
- `admin1CodesASCII` and `admin2Codes`: the names of states, provinces and nations, and of
  counties and districts.
- `DE`: Germany's own export, for its districts (Kreise), which GeoNames keeps one level lower
  than other countries' counties.
- `alternateNamesV2`: each place's and region's name in other languages, so "München" and
  "Munich", "Sachsen" and "Saxony" all work. This download is about 200 MB and is only read here,
  never shipped.

Usage:
    uv run python tools/update_places.py

GeoNames data is licensed CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/), so Jobcu
credits GeoNames in README.md and in each file's first line. Run this now and then to refresh it.
"""

import csv
import gzip
import io
import sys
import tempfile
import zipfile
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from jobcu.countries import COUNTRIES  # noqa: E402

DUMP = "https://download.geonames.org/export/dump"
DATA = ROOT / "src" / "jobcu" / "data"
TARGET = DATA / "places.csv.gz"
REGIONS = DATA / "regions.csv.gz"
CREDIT = ("# Towns with at least 1,000 inhabitants in the countries Jobcu supports, with their "
          "names in the local languages. Data © GeoNames (geonames.org), licensed CC BY 4.0. "
          "Rebuilt with tools/update_places.py. Columns: names (separated by |),country,lat,lon,"
          "people,region,district")
REGION_CREDIT = ("# The states, provinces, counties and districts of the countries Jobcu supports, "
                 "with their names in the local languages. Data © GeoNames (geonames.org), "
                 "licensed CC BY 4.0. Rebuilt with tools/update_places.py. Columns: code,level,"
                 "country,names (separated by |)")
MAX_NAMES = 6
MAX_REGION_NAMES = 8
# Countries whose districts GeoNames keeps at its third level: there the second level is a unit
# nobody uses for facts (Germany's Regierungsbezirke).
THIRD_LEVEL_DISTRICTS = ("DE",)


def download(client: httpx.Client, name: str) -> Path:
    target = Path(tempfile.gettempdir()) / name
    print(f"Downloading {DUMP}/{name} …")
    with client.stream("GET", f"{DUMP}/{name}") as response, target.open("wb") as file:
        response.raise_for_status()
        for chunk in response.iter_bytes(1 << 20):
            file.write(chunk)
    print(f"  {target.stat().st_size / 1e6:.0f} MB")
    return target


def rows_of(archive: Path, member: str):
    with zipfile.ZipFile(archive) as zipped, zipped.open(member) as raw:
        yield from csv.reader(io.TextIOWrapper(raw, encoding="utf-8"), delimiter="\t")


def rows_of_text(path: Path):
    with path.open(encoding="utf-8") as file:
        yield from csv.reader(file, delimiter="\t")


def main() -> int:
    with httpx.Client(timeout=300.0, follow_redirects=True) as client:
        cities = download(client, "cities1000.zip")
        admin1 = download(client, "admin1CodesASCII.txt")
        admin2 = download(client, "admin2Codes.txt")
        third = {country: download(client, f"{country}.zip") for country in THIRD_LEVEL_DISTRICTS}
        alternates = download(client, "alternateNamesV2.zip")

    # Regions: code → [level, country, names]; GeoNames id → code, for their other names.
    regions: dict[str, list] = {}
    region_ids: dict[str, str] = {}
    for line in rows_of_text(admin1):
        country = line[0].split(".")[0]
        if country in COUNTRIES:
            regions[line[0]] = ["region", country, [line[1], line[2]]]
            region_ids[line[3]] = line[0]
    for line in rows_of_text(admin2):
        country = line[0].split(".")[0]
        if country in COUNTRIES and country not in THIRD_LEVEL_DISTRICTS:
            regions[line[0]] = ["district", country, [line[1], line[2]]]
            region_ids[line[3]] = line[0]
    for country, archive in third.items():
        for line in rows_of(archive, f"{country}.txt"):
            if line[7] == "ADM3" and line[12]:
                code = f"{country}.K.{line[12]}"
                regions[code] = ["district", country, [line[1], line[2]]]
                region_ids[line[0]] = code

    towns: dict[str, list] = {}
    languages: dict[str, set[str]] = {}
    for line in rows_of(cities, "cities1000.txt"):
        country = line[8]
        if country not in COUNTRIES:
            continue
        names = [line[1]] + ([line[2]] if line[2] and line[2] != line[1] else [])
        region = f"{country}.{line[10]}" if f"{country}.{line[10]}" in regions else ""
        if country in THIRD_LEVEL_DISTRICTS:
            district = f"{country}.K.{line[12]}" if line[12] else ""
        else:
            district = f"{country}.{line[10]}.{line[11]}" if line[11] else ""
        towns[line[0]] = [names, country, f"{float(line[4]):.3f}", f"{float(line[5]):.3f}",
                          line[14] or "0", region, district if district in regions else ""]
        languages[line[0]] = {"en", *COUNTRIES[country].ad_languages}
    for code, (_, country, _) in regions.items():
        languages[code] = {"en", *COUNTRIES[country].ad_languages}

    extra: dict[str, set[str]] = {}
    for row in rows_of(alternates, "alternateNamesV2.txt"):
        if len(row) < 5:
            continue
        key = row[1] if row[1] in towns else region_ids.get(row[1])
        if key is None:
            continue
        colloquial = len(row) > 6 and row[6] == "1"
        historic = len(row) > 7 and row[7] == "1"
        if colloquial or historic or row[2] not in languages[key]:
            continue
        extra.setdefault(key, set()).add(row[3])

    written = []
    for town_id, (names, country, latitude, longitude, people, region, district) in towns.items():
        all_names = dict.fromkeys([*names, *sorted(extra.get(town_id, ()))])
        written.append(["|".join(list(all_names)[:MAX_NAMES]), country, latitude, longitude,
                        people, region, district])
    written.sort(key=lambda row: (row[1], row[0]))
    _write(TARGET, CREDIT, written)

    used = {row[5] for row in written} | {row[6] for row in written}
    region_rows = []
    for code, (level, country, names) in regions.items():
        if code not in used:
            continue
        all_names = dict.fromkeys([*names, *sorted(extra.get(code, ()))])
        region_rows.append([code, level, country,
                            "|".join(name for name in list(all_names)[:MAX_REGION_NAMES] if name)])
    region_rows.sort()
    _write(REGIONS, REGION_CREDIT, region_rows)
    print(f"{len(written):,} towns in {len({row[1] for row in written})} countries → "
          f"{TARGET.relative_to(ROOT)} ({TARGET.stat().st_size / 1024:.0f} KB); "
          f"{len(region_rows):,} regions → {REGIONS.relative_to(ROOT)} "
          f"({REGIONS.stat().st_size / 1024:.0f} KB)")
    return 0


def _write(target: Path, credit: str, rows: list[list[str]]) -> None:
    buffer = io.StringIO()
    buffer.write(credit + "\n")
    csv.writer(buffer, lineterminator="\n").writerows(rows)
    target.parent.mkdir(parents=True, exist_ok=True)
    with gzip.GzipFile(target, "wb", compresslevel=9, mtime=0) as out:
        out.write(buffer.getvalue().encode("utf-8"))


if __name__ == "__main__":
    sys.exit(main())
