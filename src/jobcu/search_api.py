"""Internal API for starting a search, following its progress, and job states."""

import json

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from jobcu import jobstore, search
from jobcu import pool as search_pool
from jobcu.location import ConditionEdit, EditProblem
from jobcu.settings import SearchForm, load_settings, save_settings

router = APIRouter(prefix="/api")


@router.get("/search/form")
def get_form() -> dict:
    return load_settings().search_form.model_dump()


@router.post("/search")
def start_search(form: SearchForm) -> dict:
    if not form.job_types:
        raise HTTPException(status_code=400, detail="Please tick at least one job type.")
    settings = load_settings()
    settings.search_form = form
    save_settings(settings)
    try:
        run = search.manager.start(form)
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail="A search is already running.") from exc
    return run.snapshot()


@router.get("/search/current")
def current_search() -> dict:
    """The running or last search. After a restart, the last saved results."""
    run = search.manager.current
    if run is not None:
        snapshot = run.snapshot()
    else:
        saved = jobstore.latest_results()
        if saved is None:
            return {"search": None}
        snapshot = json.loads(saved[1])
    _refresh_states(snapshot)
    # The conditions can be corrected afterwards only while Jobcu keeps that search's jobs.
    snapshot["can_edit_conditions"] = (
        snapshot["status"] != "running" and "location" in snapshot["result"]
        and search_pool.exists(snapshot["id"])
    )
    return {"search": snapshot}


class ConditionEdits(BaseModel):
    conditions: list[ConditionEdit] = Field(max_length=20)


@router.post("/search/{search_id}/conditions")
def change_conditions(search_id: int, body: ConditionEdits) -> dict:
    """Applies corrected location conditions to the jobs the latest search found."""
    try:
        run = search.manager.reapply(search_id, body.conditions)
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail="A search is already running.") from exc
    except LookupError as exc:
        raise HTTPException(
            status_code=404,
            detail="Jobcu no longer has the jobs of that search. Please search again.",
        ) from exc
    except EditProblem as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return run.snapshot()


class Answer(BaseModel):
    yes: bool


@router.post("/search/{search_id}/answer")
def answer_question(search_id: int, body: Answer) -> dict:
    run = search.manager.current
    if run is None or run.id != search_id:
        raise HTTPException(status_code=404, detail="That search isn't running any more.")
    return {"accepted": run.answer(body.yes)}


@router.post("/search/{search_id}/stop")
def stop_search(search_id: int) -> dict:
    return {"stopping": search.manager.stop(search_id)}


class StateChange(BaseModel):
    saved: bool | None = None
    applied: bool | None = None
    dismissed: bool | None = None


@router.post("/jobs/{job_id}/state")
def change_state(job_id: int, change: StateChange) -> dict:
    changes = {k: v for k, v in change.model_dump().items() if v is not None}
    if not changes:
        raise HTTPException(status_code=400, detail="Nothing to change.")
    try:
        state = jobstore.set_state(job_id, **changes)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Unknown job.") from exc
    return {"job_id": job_id, "state": state.__dict__}


@router.get("/jobs/marked/{kind}")
def marked_jobs(kind: str) -> dict:
    if kind not in ("saved", "applied"):
        raise HTTPException(status_code=404, detail="Unknown list.")
    return {"cards": jobstore.marked_cards(kind)}


def _refresh_states(snapshot: dict) -> None:
    jobs = (snapshot.get("result") or {}).get("jobs")
    if not jobs:
        return
    cards = jobs["cards"] + jobs["date_unknown"] + jobs["hidden"]
    states = jobstore.states([card["job_id"] for card in cards])
    for card in cards:
        state = states.get(card["job_id"])
        if state is not None:
            card["state"] = state.__dict__
