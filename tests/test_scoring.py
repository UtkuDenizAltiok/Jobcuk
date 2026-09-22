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
    adapter = Scripted(lambda r: {"clearly_unrelated": ["J1", "J99", "nonsense"], "places": []})
    found = groups("Hardware Engineer", "Nurse")
    assert quick_pass(client(adapter), PROFILE, found, [0, 1]).unrelated == [1]


def country_only(title, text, where="Deutschland", job_id="0"):
    return FoundJob(source="adzuna", source_job_id=job_id, url="https://x", title=title,
                    company="Rosenxt", location_text=where, country="DE", description=text)


def test_the_quick_pass_reads_the_town_an_ad_names_when_its_site_gave_only_a_country():
    jobs = [
        country_only("Hardwareentwickler (m/w/d)", "Zur Verstärkung unseres Teams suchen wir am "
                     "Standort in Wietmarschen-Lohne einen Hardwareentwickler.", job_id="0"),
        country_only("Elektroniker (m/w/d)", "Wir suchen Verstärkung in Bremen.", job_id="1"),
        country_only("Engineer", "An exciting role.", job_id="2"),  # names no town
        country_only("Nurse", "Pflege in Köln.", job_id="3"),  # unrelated: not asked about
        FoundJob(source="s", source_job_id="4", url="https://x", title="Engineer",
                 location_text="Dresden", country="DE", description="Kommen Sie nach Leipzig!"),
    ]
    found = group_duplicates(jobs, {"adzuna": "aggregator", "s": "job_board"})
    order = {group.main.source_job_id: i for i, group in enumerate(found)}
    j = {key: f"J{index}" for key, index in order.items()}
    answer = {"clearly_unrelated": [j["3"]], "places": [
        {"id": j["0"], "places": ["Wietmarschen-Lohne"]},
        # Guesses are dropped: a town the text doesn't name, a country, an unrelated job's town.
        {"id": j["1"], "places": ["Hamburg", "Deutschland", "Bremen"]},
        {"id": j["2"], "places": ["Munich"]},
        {"id": j["3"], "places": ["Köln"]},
        {"id": j["4"], "places": ["Leipzig"]},  # its site already said Dresden
    ]}
    adapter = Scripted(lambda r: answer)
    result = quick_pass(client(adapter), PROFILE, found, list(range(len(found))))
    (prompt,) = adapter.prompts
    marked = re.findall(r"^(J\d+) \|.*\| WHERE\?$", prompt, re.MULTILINE)
    assert sorted(marked) == sorted(j[key] for key in ("0", "1", "2", "3"))
    assert result.unrelated == [order["3"]]
    assert result.places == {order["0"]: ["Wietmarschen-Lohne"], order["1"]: ["Bremen"],
                             order["2"]: [], order["3"]: []}


def test_employer_page_becomes_the_main_link_unless_it_is_an_agency():
    from datetime import UTC, datetime

    from jobcu.pipeline import build_card

    def card_for(company):
        job = FoundJob(source="s", source_job_id="1", url="https://board.test/1",
                       title="Hardware Engineer", company=company,
                       employer_url="https://careers.example/1")
        group = group_duplicates([job], {"s": "job_board"})[0]
        return build_card(group, job_id=1, is_new=True, state=None, scored=None, plan=PLAN,
                          source_names={"s": "Board"}, possible_duplicate_of=None,
                          started_at=datetime.now(UTC), posted_within_hours=24)

    employer = card_for("Acme GmbH")
    assert employer["main_link"] == {"source": "Employer's site", "url": "https://careers.example/1"}
    assert employer["also_on"] == [{"source": "Board", "url": "https://board.test/1"}]
    agency = card_for("Brunel GmbH")
    assert agency["main_link"]["source"] == "Board"


def test_a_career_site_job_links_to_the_employer_once():
    from datetime import UTC, datetime

    from jobcu.pipeline import build_card

    own = FoundJob(source="greenhouse", source_job_id="acme/1", url="https://careers.example/1",
                   title="Hardware Engineer", company="Acme", location_text="Dublin, Ireland",
                   employer_url="https://careers.example/1")
    board = FoundJob(source="s", source_job_id="9", url="https://board.test/9",
                     title="Hardware Engineer", company="Acme", location_text="Dublin, Ireland")
    group = group_duplicates([board, own], {"s": "job_board", "greenhouse": "employer"})[0]
    card = build_card(group, job_id=1, is_new=True, state=None, scored=None, plan=PLAN,
                      source_names={"s": "Board", "greenhouse": "Company career sites"},
                      possible_duplicate_of=None, started_at=datetime.now(UTC),
                      posted_within_hours=24)
    assert card["main_link"] == {"source": "Employer's site", "url": "https://careers.example/1"}
    assert card["also_on"] == [{"source": "Board", "url": "https://board.test/9"}]
