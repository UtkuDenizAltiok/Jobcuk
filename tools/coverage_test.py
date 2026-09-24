"""Measures how many real jobs Jobcu found (HANDOVER section 9.0, point 5).

You give it a list of jobs you found yourself — on LinkedIn, StepStone, Indeed, a company's own
page, anywhere — for a search you have already run in Jobcu. It says how many of them Jobcu found,
and for each one it missed, at which step it was lost: never collected by any source, left out
as clearly unrelated by the quick check, or left out by a place condition. The latest search's
every collected job is kept (`pool.py`), so the tool can tell these apart for that search.

Write the list as a plain text file, one job per line:

    Company | Job title | Place | https://link (the link is optional)

A company known by two names can be written "Össur / Embla Medical". A job counts as found only
when the company, the title and (when both are known) the town agree: another job of the same
company elsewhere doesn't count.

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
from jobcu import places as place_list  # noqa: E402
from jobcu import pool as search_pool  # noqa: E402
from jobcu.dedupe import normal_company, normal_title  # noqa: E402
from jobcu.location import Place  # noqa: E402
from jobcu.sources.careers import load_directory  # noqa: E402
from jobcu.sources.matching import matches_places, matches_terms  # noqa: E402

TITLE_MATCH = 80  # a bit looser than the duplicate rules: wording differs between sites
COMPANY_MATCH = 80
SAME_PLACE_KM = 30


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
    links = [card.get("main_link", {}).get("url", ""),
             *(link.get("url", "") for link in card.get("also_on") or [])]
    if wanted.url and wanted.url.strip() in {link.strip() for link in links}:
        return 100
    return same_job(wanted, card.get("title"), card.get("company"), card.get("location"))


def same_job(wanted: Wanted, title: str | None, company: str | None,
             location: str | None) -> int:
    """0 to 100: the company (or one of its names), the title and the town must all agree."""
    names = [name for name in wanted.company.split(" / ") if name.strip()] or [wanted.company]
    company_score = max(fuzz.token_set_ratio(normal_company(name), normal_company(company))
                        for name in names)
    if company_score < COMPANY_MATCH:
        return 0
    title_score = fuzz.token_set_ratio(normal_title(wanted.title), normal_title(title))
    if not different_places(wanted.place, location):
        return min(company_score, title_score)
    return 0


def different_places(wanted: str, found: str | None) -> bool:
    """True only when both places are known towns far apart (Zenovo's Bristol job isn't its Derby
    one, search 9)."""
    a, b = place_list.locate(wanted), place_list.locate(found)
    return a is not None and b is not None and place_list.distance_km(a, b) > SAME_PLACE_KM


def lost_at(wanted: Wanted, snapshot: dict, pool: search_pool.Pool | None) -> str | None:
    """Where a job Jobcu collected was left out, or None when it was never collected (or the
    pool of collected jobs isn't kept for this search)."""
    jobs = snapshot.get("result", {}).get("jobs", {})
    for card in jobs.get("ruled_out_by_conditions", []):
        if looks_like(wanted, card) >= TITLE_MATCH:
            checks = [check for check in card.get("location_checks") or []
                      if check.get("status") not in ("verified", "fits")]
            detail = "; ".join(check.get("detail") or "" for check in checks).strip("; ")
            return ("collected, then left out by a place condition"
                    + (f" ({detail})" if detail else ""))
    for job in (pool.jobs if pool else []):
        main = job.group.main
        if same_job(wanted, main.title, main.company, main.location_text) < TITLE_MATCH:
            continue
        seen = f"collected as \"{main.title}\""
        if job.unrelated:
            return f"{seen}, then left out as clearly unrelated by the quick check"
        if job.scored is None:
            return f"{seen}, but not scored (the scoring limit)"
        return (f"{seen} and scored {job.scored.get('score')}, but not shown (hidden, or a "
                "condition decided later)")
    return None


def why_missed(wanted: Wanted, snapshot: dict, pool: search_pool.Pool | None = None) -> str:
    lost = lost_at(wanted, snapshot, pool)
    if lost:
        return lost
    result = snapshot.get("result", {})
    prefix = "never collected: " if pool is not None else ""
    terms = [Term(**term) for term in result.get("search_words", [])]
    languages = {term.language for term in terms}
    if terms and not matches_terms(terms, languages, wanted.title):
        return prefix + "the title matches none of the search words"
    unrelated = result.get("jobs", {}).get("counts", {}).get("unrelated_titles", [])
    if pool is None and any(
            fuzz.token_set_ratio(normal_title(wanted.title), normal_title(t)) >= TITLE_MATCH
            for t in unrelated):
        return "the quick check left this title out as clearly unrelated"
    plan = result.get("location", {})
    places = [Place(**place) for place in plan.get("places", [])]
    if wanted.place and places:
        fits = any(matches_places(places, place.country, wanted.place) for place in places)
        if not fits:
            return prefix + "the place isn't one of the places searched"
    directory = {normal_company(e.name) for e in load_directory()}
    if any(normal_company(name) in directory for name in wanted.company.split(" / ")):
        return (prefix + "the company is in the employer directory, so its career site was "
                "read: the job may be older than the window there, or its title didn't match")
    return prefix + ("no source Jobcu uses had it, or the fixed rules left it out (older than "
                     "the window on the site Jobcu read, or a job type not ticked)")


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
    pool = search_pool.load(search_id)  # kept for the latest search only
    if pool is None:
        print("(Every collected job is kept only for the latest search, so the reasons below "
              "are guesses.)")
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
        print(f"      {'' if pool else 'probably because '}{why_missed(job, snapshot, pool)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
