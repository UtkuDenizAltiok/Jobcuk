import json
import re

from jobcu.ai.base import ProviderAdapter, RawReply, Usage
from jobcu.ai.client import AIClient
from jobcu.dedupe import group_duplicates
from jobcu.location import LocationPlan
from jobcu.profile import Profile
from jobcu.relevance import quick_pass
from jobcu.scoring import JobScore, finish, score_groups
from jobcu.settings import Settings
from jobcu.sources.base import FoundJob

PROFILE = Profile.model_validate({
    "summary": "Hardware engineer.", "current_or_last_role": None, "field": "Electronics",
    "skills": [], "technical_areas": [], "years_full_time_experience": 0,
    "years_student_or_part_time_experience": 2, "experience_note": "", "seniority": "junior",
    "education": [], "languages": [], "target_roles": ["Hardware Engineer"],
    "target_fields": [], "preferences": [], "work_mode_preference": "not_stated",
    "dealbreakers": [], "work_authorisation": None, "ignored_as_application_specific": [],
})
PLAN = LocationPlan(text="", understood_as="Anywhere.", countries=["DE"], places=[],
                    not_checked_yet=[], outside_supported_area=[], broad=True)


def score_json(job_id, role=30):
    return {"job_id": job_id, "role_and_skills": role, "seniority": 15, "languages": 15,
            "hard_requirements": 15, "location_and_preferences": 8, "reasons": ["Good match"],
            "job_type": "unclear", "work_mode": "hybrid", "fully_remote": False,
            "required_languages": []}


class Scripted(ProviderAdapter):
    def __init__(self, answer):
        super().__init__("fake")
        self.answer = answer
        self.prompts = []

    def complete_json(self, **request):
        self.prompts.append(request["prompt"])
        return RawReply(json.dumps(self.answer(request)), Usage(1, 1))

    def list_models(self):
        return []


def client(adapter):
    settings = Settings()
    settings.ai.provider = "gemini"
    settings.ai.model = "m"
    return AIClient(settings, adapter=adapter)


def groups(*titles):
    jobs = [FoundJob(source="s", source_job_id=str(i), url="https://x", title=t,
                     company=f"C{i}", description="Ad text") for i, t in enumerate(titles)]
    return group_duplicates(jobs, {"s": "job_board"})


def test_total_is_added_up_in_code_and_parts_are_kept_within_their_maximum():
    raw = JobScore.model_validate({**score_json("J1", role=55), "reasons": ["a", "b", "c", "d"]})
    result = finish(raw)
    assert result["parts"]["role_and_skills"] == 40
    assert result["score"] == 40 + 15 + 15 + 15 + 8
    assert result["reasons"] == ["a", "b", "c"]
    assert result["job_type"] is None and result["work_mode"] == "hybrid"


def test_every_job_in_a_batch_gets_a_score_even_if_the_ai_skips_one():
    def answer(request):
        ids = re.findall(r"JOB (J\d+)", request["prompt"])
        return {"scores": [score_json(ids[0])]}  # always leaves out the other jobs

    adapter = Scripted(answer)
    found = groups("Hardware Engineer", "Electronics Engineer")
    results = score_groups(client(adapter), PROFILE, PLAN, found, [0, 1], batch_size=2)
    assert set(results) == {0, 1}
    assert len(adapter.prompts) == 2  # the skipped job was asked about on its own


def test_scoring_prompt_includes_the_profile_and_marks_short_ads():
    adapter = Scripted(lambda r: {"scores": [score_json("J0")]})
    score_groups(client(adapter), PROFILE, PLAN, groups("Hardware Engineer"), [0])
    prompt = adapter.prompts[0]
    assert "Hardware Engineer" in prompt and "THE PERSON'S PROFILE" in prompt
    assert "only the start of the ad is available" in prompt


def test_quick_pass_only_accepts_ids_it_was_given():
    adapter = Scripted(lambda r: {"clearly_unrelated": ["J1", "J99", "nonsense"]})
    found = groups("Hardware Engineer", "Nurse")
    assert quick_pass(client(adapter), PROFILE, found, [0, 1]) == [1]
