import json

import pytest

from jobcu import db, jobstore
from jobcu.dedupe import group_duplicates
from jobcu.sources.base import FoundJob


def group(source="a", job_id="1", title="Hardware Engineer", company="Acme"):
    job = FoundJob(source=source, source_job_id=job_id, url="https://x", title=title,
                   company=company, location_text="Berlin")
    return group_duplicates([job], {source: "job_board"})[0]


def new_search() -> int:
    with db.connect() as conn:
        return conn.execute(
            "INSERT INTO searches (status, form_json) VALUES ('running', '{}')"
        ).lastrowid


def test_jobs_are_new_once_and_recognised_again_through_any_copy():
    first = new_search()
    ids, new = jobstore.remember([group("a", "1")], first)
    assert new == [True]
    second = new_search()
    # Same job, found on another source with another id: recognised by company and title.
    again, new_again = jobstore.remember([group("b", "77")], second)
    assert again == ids and new_again == [False]


def test_states_are_saved_and_listed():
    ids, _ = jobstore.remember([group()], new_search())
    jobstore.save_cards([{"job_id": ids[0], "title": "Hardware Engineer"}])
    jobstore.set_state(ids[0], saved=True)
    assert jobstore.states(ids)[ids[0]].saved
    assert [c["title"] for c in jobstore.marked_cards("saved")] == ["Hardware Engineer"]
    assert jobstore.marked_cards("applied") == []
    jobstore.set_state(ids[0], saved=False, dismissed=True)
    state = jobstore.states(ids)[ids[0]]
    assert not state.saved and state.dismissed


def test_unknown_job_state_change_is_refused():
    with pytest.raises(KeyError):
        jobstore.set_state(12345, saved=True)


def test_latest_results_are_kept():
    search_id = new_search()
    jobstore.save_results(search_id, json.dumps({"id": search_id}))
    assert jobstore.latest_results() == (search_id, json.dumps({"id": search_id}))
