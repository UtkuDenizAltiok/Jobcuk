"""Rebuilds the list of towns Jobcu ships (src/jobcu/data/places.csv.gz).

Jobcu needs coordinates for towns so it can tell how far a job is from the place someone asked
for, when a job source gives only a place name. The list comes from GeoNames' free exports,
narrowed to the supported countries:

- `cities1000`: every place with at least 1,000 inhabitants, with its coordinates (10 MB).
- `alternateNamesV2`: each place's name in other languages, so "München" and "Munich" both
  work. This download is about 200 MB and is only read here, never shipped.

Usage:
    uv run python tools/update_places.py

GeoNames data is licensed CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/), so Jobcu
credits GeoNames in README.md and in the file's first line. Run this now and then to refresh it.
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
TARGET = ROOT / "src" / "jobcu" / "data" / "places.csv.gz"
CREDIT = ("# Towns with at least 1,000 inhabitants in the countries Jobcu supports, with their "
          "names in the local languages. Data © GeoNames (geonames.org), licensed CC BY 4.0. "
          "Rebuilt with tools/update_places.py. Columns: names (separated by |),country,lat,lon,"
          "people")
MAX_NAMES = 6


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


def main() -> int:
    with httpx.Client(timeout=300.0, follow_redirects=True) as client:
        cities = download(client, "cities1000.zip")
        alternates = download(client, "alternateNamesV2.zip")

    towns: dict[str, list] = {}
    languages: dict[str, set[str]] = {}
    for line in rows_of(cities, "cities1000.txt"):
        country = line[8]
        if country not in COUNTRIES:
            continue
        names = [line[1]] + ([line[2]] if line[2] and line[2] != line[1] else [])
        towns[line[0]] = [names, country, f"{float(line[4]):.3f}", f"{float(line[5]):.3f}",
                          line[14] or "0"]
        languages[line[0]] = {"en", *COUNTRIES[country].ad_languages}

    extra: dict[str, set[str]] = {}
    for row in rows_of(alternates, "alternateNamesV2.txt"):
        if len(row) < 5 or row[1] not in towns:
            continue
        colloquial = len(row) > 6 and row[6] == "1"
        historic = len(row) > 7 and row[7] == "1"
        if colloquial or historic or row[2] not in languages[row[1]]:
            continue
        extra.setdefault(row[1], set()).add(row[3])

    written = []
    for town_id, (names, country, latitude, longitude, people) in towns.items():
        all_names = dict.fromkeys([*names, *sorted(extra.get(town_id, ()))])
        written.append(["|".join(list(all_names)[:MAX_NAMES]), country, latitude, longitude,
                        people])
    written.sort(key=lambda row: (row[1], row[0]))

    buffer = io.StringIO()
    buffer.write(CREDIT + "\n")
    csv.writer(buffer, lineterminator="\n").writerows(written)
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    with gzip.GzipFile(TARGET, "wb", compresslevel=9, mtime=0) as out:
        out.write(buffer.getvalue().encode("utf-8"))
    print(f"{len(written):,} towns in {len({row[1] for row in written})} countries → "
          f"{TARGET.relative_to(ROOT)} ({TARGET.stat().st_size / 1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
