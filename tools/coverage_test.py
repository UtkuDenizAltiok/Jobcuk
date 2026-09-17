"""Measures how many real jobs Jobcu found (HANDOVER section 9.0, point 5).

You give it a list of jobs you found yourself — on LinkedIn, StepStone, Indeed, a company's own
page, anywhere — for a search you have already run in Jobcu. It says how many of them Jobcu found,
and for each one it missed, why it probably missed it.

Write the list as a plain text file, one job per line:

    Company | Job title | Place | https://link (the link is optional)

Lines starting with # are ignored. Then run:

    uv run python tools/coverage_test.py my-list.txt              the last search
    uv run python tools/coverage_test.py my-list.txt --search 7   a particular search

It reads the searches already saved in your data folder and sends no requests anywhere.
"""

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from rapidfuzz import fuzz  # noqa: E402

from jobcu import db  # noqa: E402
from jobcu.dedupe import normal_company, normal_title  # noqa: E402
from jobcu.location import Place  # noqa: E402
from jobcu.sources.careers import load_directory  # noqa: E402
from jobcu.sources.matching import matches_places, matches_terms  # noqa: E402

TITLE_MATCH = 80  # a bit looser than the duplicate rules: wording differs between sites


@dataclass
class Wanted:
    company: str
    title: str
    place: str = ""
    url: str = ""


def read_list(path: Path) -> list[Wanted]:
    jobs = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        parts = [part.strip() for part in line.split("|")]
        if len(parts) < 2:
            print(f"Skipped (needs at least 'Company | Title'): {line}")
            continue
        jobs.append(Wanted(*(parts + ["", ""])[:4]))
    return jobs


def saved_search(search_id: int | None) -> tuple[int, dict]:
    with db.connect() as conn:
        if search_id is None:
            row = conn.execute(
                "SELECT search_id, result_json FROM search_results ORDER BY search_id DESC LIMIT 1"
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT search_id, result_json FROM search_results WHERE search_id = ?",
                (search_id,),
            ).fetchone()
    if row is None:
        raise SystemExit("No saved search found in this data folder. Run a search in Jobcu first.")
    return row["search_id"], json.loads(row["result_json"])


def found_jobs(snapshot: dict) -> list[dict]:
    jobs = snapshot.get("result", {}).get("jobs", {})
    return [*jobs.get("cards", []), *jobs.get("date_unknown", []), *jobs.get("hidden", [])]


def looks_like(wanted: Wanted, card: dict) -> int:
    """How sure we are that this card is the job on the list (0 to 100)."""
    company = fuzz.token_set_ratio(normal_company(wanted.company), normal_company(card["company"]))
    title = fuzz.token_set_ratio(normal_title(wanted.title), normal_title(card["title"]))
    if wanted.url and card.get("main_link", {}).get("url", "").strip() == wanted.url.strip():
        return 100
    return min(company, title)


def why_missed(wanted: Wanted, snapshot: dict) -> str:
    result = snapshot.get("result", {})
    terms = [Term(**term) for term in result.get("search_words", [])]
    languages = {term.language for term in terms}
    if terms and not matches_terms(terms, languages, wanted.title):
        return "the title matches none of the search words"
    unrelated = result.get("jobs", {}).get("counts", {}).get("unrelated_titles", [])
    if any(fuzz.token_set_ratio(normal_title(wanted.title), normal_title(t)) >= TITLE_MATCH
           for t in unrelated):
        return "the quick check left this title out as clearly unrelated"
    plan = result.get("location", {})
    places = [Place(**place) for place in plan.get("places", [])]
    if wanted.place and places:
        fits = any(matches_places(places, place.country, wanted.place) for place in places)
        if not fits:
            return "the place isn't one of the places searched"
    directory = {normal_company(e.name) for e in load_directory()}
    if normal_company(wanted.company) in directory:
        return ("the company is in the employer directory, so its career site was read: "
                "the job may be older than the window, or its title didn't match")
    return "no source Jobcu uses had it (or it was outside the time window)"


@dataclass
class Term:
    text: str
    language: str
    kind: str


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("list", type=Path, help="text file with the jobs you found yourself")
    parser.add_argument("--search", type=int, default=None, help="which saved search to compare")
    args = parser.parse_args()

    wanted = read_list(args.list)
    search_id, snapshot = saved_search(args.search)
    cards = found_jobs(snapshot)
    form = snapshot.get("form", {})
    print(f"Search {search_id}: \"{form.get('location_text', '')}\", "
          f"posted within {form.get('posted_within_hours')} hours, {len(cards)} jobs found.\n")

    found, missed = [], []
    for job in wanted:
        best = max(cards, key=lambda card: looks_like(job, card), default=None)
        score = looks_like(job, best) if best else 0
        if best and score >= TITLE_MATCH:
            found.append((job, best, score))
        else:
            missed.append(job)

    print(f"Jobcu found {len(found)} of {len(wanted)} ({len(found) / max(1, len(wanted)):.0%}).\n")
    for job, card, score in found:
        print(f"  ✓ {job.company} — {job.title}")
        print(f"      as \"{card['title']}\" ({card['main_link']['source']}, "
              f"score {card['score']}, match {score})")
    if missed:
        print("\nMissed:")
    for job in missed:
        print(f"  ✗ {job.company} — {job.title} ({job.place})")
        print(f"      probably because {why_missed(job, snapshot)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
