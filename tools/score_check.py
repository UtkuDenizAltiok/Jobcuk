"""Measures Jobcu's scoring against your own judgement (HANDOVER section 13).

Answer a few jobs on the **Score check** screen in Jobcu first (good / okay / poor, and whether a
title Jobcu left out was really unrelated). Then:

    uv run python tools/score_check.py                  compare the scores Jobcu already gave
    uv run python tools/score_check.py --rescore        score the same ads again, now
    uv run python tools/score_check.py --rescore --batch 1 --effort medium --summary

`--rescore` uses your AI provider and costs tokens; the other form is free. The options exist to
compare settings: batch size, reasoning effort, and scoring from a short summary instead of the
full ad. Everything stays in your data folder.
"""

import argparse
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from jobcu import documents, quality  # noqa: E402
from jobcu.ai.client import AIClient  # noqa: E402
from jobcu.ai.usage import UsageLog, total_tokens  # noqa: E402
from jobcu.dedupe import group_duplicates  # noqa: E402
from jobcu.keystore import KeyStore  # noqa: E402
from jobcu.location import LocationPlan  # noqa: E402
from jobcu.profile import read_profile_reusing  # noqa: E402
from jobcu.scoring import score_groups  # noqa: E402
from jobcu.settings import load_settings  # noqa: E402
from jobcu.sources.base import FoundJob  # noqa: E402

# What a rating means in points, for judging whether a score is in the right region.
BANDS = {"good": (70, 100), "okay": (45, 85), "poor": (0, 60)}


def as_job(ad: quality.Ad) -> FoundJob:
    return FoundJob(source=ad.kind, source_job_id=str(ad.id), url=ad.url, title=ad.title,
                    company=ad.company, location_text=ad.location, description=ad.text,
                    description_is_complete=True)


def rescore(ads: list[quality.Ad], batch: int, effort: str | None, summary: bool) -> dict[int, int]:
    settings = load_settings()
    if effort:
        settings.ai.scoring_effort = effort
    client = AIClient(settings, KeyStore(), usage_log=UsageLog(), notify=print)
    profile, reused = read_profile_reusing(
        client, documents.read_text("cv"), documents.read_text("cover_letter")
    )
    print(f"Profile: {profile.current_or_last_role or profile.field}"
          f"{' (reused)' if reused else ''}")
    plan = LocationPlan(text="", understood_as="Anywhere.", countries=[], places=[],
                        not_checked_yet=[], outside_supported_area=[], broad=True)
    groups = []
    for ad in ads:
        job = as_job(ad)
        if summary:
            job = FoundJob(**{**job.__dict__, "description": job.description[:600],
                              "description_is_complete": False})
        groups.append(group_duplicates([job], {ad.kind: "job_board"})[0])
    before = total_tokens(UsageLog().this_month())
    scored = score_groups(client, profile, plan, groups, list(range(len(groups))),
                          batch_size=batch)
    used = total_tokens(UsageLog().this_month()) - before
    print(f"Scored {len(scored)} ads with batch {batch}, effort "
          f"{settings.ai.scoring_effort or 'default'}, "
          f"{'summary' if summary else 'full ad'}: {used:,} tokens\n")
    return {ads[index].id: result["score"] for index, result in scored.items()}


def report(ads: list[quality.Ad], scores: dict[int, int]) -> None:
    rated = [ad for ad in ads if ad.kind == "scored" and ad.rating and ad.id in scores]
    if not rated:
        print("No answered jobs with scores yet. Open the Score check screen in Jobcu first.")
        return
    print(f"{len(rated)} answered jobs\n")
    in_band, rows = 0, []
    for ad in sorted(rated, key=lambda a: -scores[a.id]):
        low, high = BANDS[ad.rating]
        score = scores[ad.id]
        fits = low <= score <= high
        in_band += fits
        rows.append((score, ad.rating, fits, ad))
    for score, rating, fits, ad in rows:
        mark = "ok " if fits else "OFF"
        print(f"  {mark} {score:3}  you said {rating:5}  {ad.title[:52]:52} {ad.company or ''}")
    print(f"\nIn the region you'd expect: {in_band} of {len(rated)} "
          f"({in_band / len(rated):.0%})")
    for rating in ("good", "okay", "poor"):
        group = [score for score, r, _, _ in rows if r == rating]
        if group:
            print(f"  you said {rating:5}: scores {min(group)}–{max(group)}, "
                  f"median {statistics.median(group):.0f}")
    worst = [row for row in rows if not row[2]]
    if worst:
        print("\nThe ones to look at first (the prompt may need tuning):")
        for score, rating, _, ad in worst[:5]:
            print(f"  {score:3} but you said {rating}: {ad.title[:60]}")

    titles = [ad for ad in ads if ad.kind == "title_only" and ad.rating]
    if titles:
        wrong = [ad for ad in titles if ad.rating == "worth_a_look"]
        print(f"\nQuick check: of {len(titles)} answered titles it left out, you'd have looked at "
              f"{len(wrong)}.")
        for ad in wrong[:5]:
            print(f"  ✗ {ad.title[:60]} ({ad.company or ''})")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--rescore", action="store_true", help="score the ads again now")
    parser.add_argument("--batch", type=int, default=4, help="jobs per AI request when rescoring")
    parser.add_argument("--effort", default=None,
                        choices=["minimal", "low", "medium", "high"])
    parser.add_argument("--summary", action="store_true",
                        help="score from the first 600 characters instead of the full ad")
    args = parser.parse_args()

    ads = quality.all_ads()
    scored_ads = [ad for ad in ads if ad.kind == "scored"]
    if args.rescore and scored_ads:
        scores = rescore(scored_ads, args.batch, args.effort, args.summary)
    else:
        scores = {ad.id: ad.score for ad in scored_ads if ad.score is not None}
        print("Using the scores Jobcu gave during your searches.\n")
    report(ads, scores)
    return 0


if __name__ == "__main__":
    sys.exit(main())
