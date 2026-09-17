"""Duplicates and the main link (HANDOVER section 10).

- One card per real job, even when it's posted in several places.
- Copies match on normalised company, job title and location; when both copies carry a
  full ad, similar descriptions also confirm a match.
- Ads from staffing agencies that hide the employer are tagged "possible duplicate"
  instead of being merged, because they may or may not be the same job.
- The main link prefers the employer's own page, then LinkedIn, then job boards, then
  aggregators. The other copies become "Also on".
"""

import math
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime

from rapidfuzz import fuzz

from jobcu.freshness import earliest_possible
from jobcu.sources.base import FoundJob

TITLE_MATCH = 90
TITLE_MATCH_WITH_TEXT = 85
TEXT_MATCH = 0.8
AGENCY_TEXT_MATCH = 0.5
NEARBY_KM = 30

SOURCE_KIND_RANK = {"employer": 0, "linkedin": 1, "job_board": 2, "aggregator": 3}

_LEGAL_FORMS = re.compile(
    r"\b(gmbh|mbh|ag|se|kg|kgaa|ohg|ug|co|e\.?\s?v|ltd|limited|plc|llp|inc|llc|corp|corporation"
    r"|company|bv|b\.v|nv|n\.v|sa|s\.a|sas|sarl|spa|s\.p\.a|srl|s\.r\.l|ab|as|a/s|asa|oy|oyj"
    r"|aps|sp\.?\s?z\.?\s?o\.?\s?o|holding|group|gruppe|deutschland|germany|uk|ireland)\b\.?"
)
_GENDER_MARKERS = re.compile(
    r"\((?:[mwdfxi]\s*/\s*){1,3}[mwdfxi]\)|\b(?:[mwdfx]/){2}[mwdfx]\b|\(all genders?\)"
    r"|\(gn\)|\*in\b|/in\b",
    re.IGNORECASE,
)
# Words in company names that usually mean a staffing or recruitment agency.
_AGENCY_WORDS = re.compile(
    r"recruit|staffing|personal(?:service|dienst|leasing|beratung| gmbh|\b)|personnel|zeitarbeit"
    r"|arbeitnehmerüberlassung|headhunt|talent|resourc|consult|search partners|placement"
    r"|\b(?:ferchau|brunel|hays|akkodis|randstad|adecco|manpower|gulp|orizon|expertum|amadeus fire"
    r"|dis ag|jobvector|avantgarde experts|michael page|page personnel|robert half|kelly services"
    r"|harvey nash|nigel frank|computer futures|jonathan lee|matchtech|gi group"
    r"|synergie|start people|tempo-team)\b",
    re.IGNORECASE,
)

# Words that make two otherwise similar titles different jobs.
_LEVEL_WORDS = re.compile(
    r"\b(senior|sr|junior|jr|lead|principal|staff|head|chief|director|manager|intern|internship"
    r"|trainee|graduate|werkstudent|werkstudentin|praktikant|praktikum|abschlussarbeit|thesis"
    r"|leiter|leitung|teamleiter|apprentice|ausbildung)\b"
)


_REFERENCE_NUMBERS = re.compile(r"\b\d{3,}\b")


def title_similarity(a: str, b: str) -> float:
    """0–100. Titles at a different level ("Senior") or with different reference numbers
    never count as the same job."""
    if set(_LEVEL_WORDS.findall(a)) != set(_LEVEL_WORDS.findall(b)):
        return 0.0
    if set(_REFERENCE_NUMBERS.findall(a)) != set(_REFERENCE_NUMBERS.findall(b)):
        return 0.0
    # Every word needs a close partner in the other title: this allows typos ("Desig") but not
    # different words that look alike ("Elektronik" and "Elektrotechnik").
    words_a, words_b = set(a.split()), set(b.split())
    for one, other in ((words_a, words_b), (words_b, words_a)):
        for word in one:
            if not any(fuzz.ratio(word, candidate) >= 90 for candidate in other):
                return 0.0
    return fuzz.token_sort_ratio(a, b)


# English and local names of big cities, so "Munich" and "München" count as one place.
_CITY_ALIASES = {
    "munchen": "munich", "koln": "cologne", "nurnberg": "nuremberg", "wien": "vienna",
    "zurich": "zurich", "geneve": "geneva", "bruxelles": "brussels", "brussel": "brussels",
    "lisboa": "lisbon", "praha": "prague", "warszawa": "warsaw", "roma": "rome",
    "milano": "milan", "kobenhavn": "copenhagen", "goteborg": "gothenburg",
    "den haag": "the hague", "hannover": "hanover", "frankfurt am main": "frankfurt",
    "baile atha cliath": "dublin", "corcaigh": "cork", "luimneach": "limerick",
    "gaillimh": "galway",
}


def fold(text: str | None) -> str:
    """Lower case, without accents or punctuation."""
    if not text:
        return ""
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = re.sub(r"[^a-z0-9/ ]+", " ", text.lower())
    return " ".join(text.split())


def normal_company(name: str | None) -> str:
    return " ".join(_LEGAL_FORMS.sub(" ", fold(name).replace("&", " ")).split())


def normal_title(title: str | None) -> str:
    return fold(_GENDER_MARKERS.sub(" ", title or ""))


def normal_city(location: str | None) -> str:
    first = fold((location or "").split(",")[0])
    return _CITY_ALIASES.get(first, first)


def is_agency(company: str | None) -> bool:
    return bool(company and _AGENCY_WORDS.search(company))


@dataclass
class JobGroup:
    """One real job, with all the copies found of it."""

    copies: list[FoundJob]
    possible_duplicate_of: int | None = None  # index of the group this may repeat
    source_kinds: dict[str, str] = field(default_factory=dict)

    @property
    def main(self) -> FoundJob:
        return min(
            self.copies,
            key=lambda c: (
                SOURCE_KIND_RANK.get(self.source_kinds.get(c.source, "aggregator"), 3),
                not c.description_is_complete,
            ),
        )

    @property
    def best_description_copy(self) -> FoundJob:
        return max(self.copies, key=lambda c: (c.description_is_complete, len(c.description)))

    @property
    def earliest_copy(self) -> FoundJob | None:
        dated = [(earliest_possible(c.posted_at, c.date_precision), c) for c in self.copies]
        dated = [(when, c) for when, c in dated if when is not None]
        return min(dated, key=lambda pair: pair[0])[1] if dated else None

    @property
    def posted_at(self) -> datetime | None:
        copy = self.earliest_copy
        return copy.posted_at if copy else None

    @property
    def date_precision(self) -> str:
        copy = self.earliest_copy
        return copy.date_precision if copy else "unknown"


def group_duplicates(jobs: list[FoundJob], source_kinds: dict[str, str]) -> list[JobGroup]:
    parent = list(range(len(jobs)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(a: int, b: int) -> None:
        parent[find(a)] = find(b)

    companies = [normal_company(j.company) for j in jobs]
    titles = [normal_title(j.title) for j in jobs]
    cities = [normal_city(j.location_text) for j in jobs]

    # The same ad from the same source is always one job.
    by_source_id: dict[tuple[str, str], int] = {}
    for i, job in enumerate(jobs):
        key = (job.source, job.source_job_id)
        if key in by_source_id:
            union(i, by_source_id[key])
        else:
            by_source_id[key] = i

    # Compare jobs of the same company only, which keeps this fast.
    by_company: dict[str, list[int]] = {}
    for i, company in enumerate(companies):
        if company:
            by_company.setdefault(company, []).append(i)
    for members in by_company.values():
        for n, a in enumerate(members):
            for b in members[n + 1 :]:
                if find(a) == find(b) or not _same_place(jobs[a], jobs[b], cities[a], cities[b]):
                    continue
                title_score = title_similarity(titles[a], titles[b])
                if is_agency(jobs[a].company):
                    # Agencies post near-identical ads for different clients: the text must match.
                    if title_score >= TITLE_MATCH and _both_full_and_similar(
                        jobs[a], jobs[b], TEXT_MATCH
                    ):
                        union(a, b)
                elif title_score >= TITLE_MATCH:
                    union(a, b)
                elif title_score >= TITLE_MATCH_WITH_TEXT and _both_full_and_similar(
                    jobs[a], jobs[b], TEXT_MATCH
                ):
                    union(a, b)

    grouped: dict[int, list[int]] = {}
    for i in range(len(jobs)):
        grouped.setdefault(find(i), []).append(i)
    groups = [JobGroup([jobs[i] for i in members], source_kinds=source_kinds)
              for members in grouped.values()]
    _tag_agency_repeats(groups)
    return groups


def _same_place(a: FoundJob, b: FoundJob, city_a: str, city_b: str) -> bool:
    if a.country and b.country and a.country != b.country:
        return False
    if None not in (a.latitude, a.longitude, b.latitude, b.longitude):
        return _distance_km(a.latitude, a.longitude, b.latitude, b.longitude) <= NEARBY_KM
    # A location like "Germany" or a missing one can't rule a match out.
    return not city_a or not city_b or city_a == city_b or city_a in city_b or city_b in city_a


def _distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def _shingles(text: str, size: int = 5) -> set[str]:
    words = fold(text).split()
    return {" ".join(words[i : i + size]) for i in range(max(0, len(words) - size + 1))}


def _text_similarity(a: str, b: str) -> float:
    sa, sb = _shingles(a), _shingles(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / min(len(sa), len(sb))


def _both_full_and_similar(a: FoundJob, b: FoundJob, threshold: float) -> bool:
    return (
        a.description_is_complete
        and b.description_is_complete
        and _text_similarity(a.description, b.description) >= threshold
    )


def _tag_agency_repeats(groups: list[JobGroup]) -> None:
    """Agency ads that closely match an employer's own ad are flagged, not merged."""
    employer_groups = [
        (i, g) for i, g in enumerate(groups) if not is_agency(g.main.company)
    ]
    for group in groups:
        main = group.main
        if not is_agency(main.company):
            continue
        title = normal_title(main.title)
        for i, other in employer_groups:
            candidate = other.main
            if main.country and candidate.country and main.country != candidate.country:
                continue
            if title_similarity(title, normal_title(candidate.title)) < TITLE_MATCH_WITH_TEXT:
                continue
            best = group.best_description_copy
            other_best = other.best_description_copy
            if _text_similarity(best.description, other_best.description) >= AGENCY_TEXT_MATCH:
                group.possible_duplicate_of = i
                break
