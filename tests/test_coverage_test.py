"""tools/coverage_test.py: which listed jobs Jobcu found, and at which step it lost the others.

Search 9 (2026-09-24): the tool looked only at the cards, so jobs never collected were blamed on
the quick check or the search words, and Zenovo's Bristol job counted as its Derby one."""

import importlib.util
from pathlib import Path

from jobcu.dedupe import JobGroup
from jobcu.pool import Pool, PoolJob
from jobcu.sources.base import FoundJob

TOOL = Path(__file__).resolve().parent.parent / "tools" / "coverage_test.py"


def load_tool():
    spec = importlib.util.spec_from_file_location("coverage_test", TOOL)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def card(title, company, location, url="https://jobs.test/1"):
    return {"title": title, "company": company, "location": location, "score": 80,
            "main_link": {"url": url, "source": "Board"}, "also_on": []}


def pool_job(title, company, location, unrelated=None, scored=None):
    job = FoundJob(source="board", source_job_id=title, url="https://jobs.test/x", title=title,
                   company=company, location_text=location, country="GB")
    return PoolJob(JobGroup([job]), unrelated=unrelated, scored=scored)


SNAPSHOT = {"result": {"search_words": [
    {"text": "Test Engineer", "language": "en", "kind": "job_title"}],
    "jobs": {"cards": [card("Test Engineer", "Zenovo", "Bristol"),
                       card("Hardware Engineer", "Embla Medical", "Livingston")],
             "ruled_out_by_conditions": [{
                 **card("Test Engineer", "Leonardo", "Edinburgh"),
                 "location_checks": [{"status": "fails", "detail": "no such place in reach"}]}]}}}


def test_a_job_counts_as_found_only_with_the_same_company_title_and_town():
    tool = load_tool()
    cards = SNAPSHOT["result"]["jobs"]["cards"]
    derby = tool.Wanted("Zenovo", "Test Engineer", "Derby")
    bristol = tool.Wanted("Zenovo", "Test Engineer", "Bristol")
    assert max(tool.looks_like(derby, c) for c in cards) < tool.TITLE_MATCH
    assert max(tool.looks_like(bristol, c) for c in cards) >= tool.TITLE_MATCH
    # A company's other name, and a link that is the card's own.
    other_name = tool.Wanted("Össur / Embla Medical", "Hardware Engineer", "Livingston")
    assert max(tool.looks_like(other_name, c) for c in cards) >= tool.TITLE_MATCH
    by_link = tool.Wanted("Someone", "Else", "", "https://jobs.test/1")
    assert tool.looks_like(by_link, cards[0]) == 100


def test_a_missed_job_is_placed_at_the_step_that_lost_it():
    tool = load_tool()
    pool = Pool(search_id=1, jobs=[
        pool_job("Test Engineer", "Babcock", "Rosyth", unrelated=True),
        pool_job("Test Engineer", "Thales", "Glasgow", unrelated=False, scored=None)],
        profile={})
    why = {company: tool.why_missed(tool.Wanted(company, "Test Engineer", town), SNAPSHOT, pool)
           for company, town in (("Leonardo", "Edinburgh"), ("Babcock", "Rosyth"),
                                 ("Thales", "Glasgow"), ("Nobody Ltd", "Leeds"))}
    assert why["Leonardo"] == ("collected, then left out by a place condition "
                               "(no such place in reach)")
    assert "left out as clearly unrelated by the quick check" in why["Babcock"]
    assert "not scored" in why["Thales"]
    assert why["Nobody Ltd"].startswith("never collected: no source Jobcu uses had it")
    # A title none of the search words match is named as the reason it was never collected.
    assert tool.why_missed(tool.Wanted("Nobody Ltd", "RF Power Engineer", "Cork"), SNAPSHOT,
                           pool) == "never collected: the title matches none of the search words"
