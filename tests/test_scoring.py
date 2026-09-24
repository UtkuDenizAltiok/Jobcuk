import json
import re

from jobcu.ai.base import ProviderAdapter, RawReply, Usage
from jobcu.ai.client import AIClient
from jobcu.dedupe import group_duplicates
from jobcu.location import LocationPlan
from jobcu.profile import LanguageSkill, Profile
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


def score_json(job_id, role=30, **evidence):
    return {"job_id": job_id, "ad_language": "English", "languages_asked": [],
            "years_required": None, "doctorate": "not_required",
            "citizenship_or_clearance": "no_such_requirement",
            "citizenship_or_clearance_words": "", "role_and_skills": role, "seniority": 15,
            "hard_requirements": 15, "location_and_preferences": 8, "reasons": ["Good match"],
            "job_type": "unclear", "work_mode": "hybrid", "fully_remote": False, **evidence}


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
    result = finish(raw, PROFILE)
    assert result["parts"]["role_and_skills"] == 40
    assert result["score"] == 40 + 15 + 15 + 15 + 8 and result["limits"] == []
    assert result["reasons"] == ["a", "b", "c"]
    assert result["job_type"] is None and result["work_mode"] == "hybrid"


# A made-up person: fluent English, basic German, native Turkish, no full-time years yet.
SPEAKER = PROFILE.model_copy(update={
    "languages": [
        LanguageSkill(language="English", level_as_written="Fluent", cefr="C1",
                      cefr_is_estimate=True),
        LanguageSkill(language="German", level_as_written="Basic", cefr="A2",
                      cefr_is_estimate=True),
        LanguageSkill(language="Turkish", level_as_written="Native", cefr="native",
                      cefr_is_estimate=False),
    ],
    "years_full_time_experience": 0.0,
})


def asked(language, level, must_have=True):
    return {"language": language, "level": level, "must_have": must_have}


def scored(profile=SPEAKER, **evidence):
    raw = score_json("J1", role=39, **evidence)
    raw.update({"seniority": 18, "hard_requirements": 15, "location_and_preferences": 9})
    return finish(JobScore.model_validate(raw), profile)


def test_a_language_two_levels_above_gives_no_language_points_and_limits_the_total_to_65():
    # FERCHAU in search 8: "Gute Deutsch- und Englischkenntnisse", German B2+; the person has A2.
    result = scored(ad_language="German",
                    languages_asked=[asked("German", "B2"), asked("English", "B2")])
    assert result["parts"]["languages"] == 0
    assert result["score"] == 65  # the parts add up to 81
    assert result["limits"] == [{"at": 65, "why": "German B2 required, you have A2"}]
    assert result["required_languages"] == ["German B2", "English B2"]
    assert result["notes"] == []  # the ad said what it needs


def test_one_level_short_or_only_a_plus_costs_some_language_points_but_sets_no_limit():
    one_short = scored(languages_asked=[asked("German", "B1")])
    assert one_short["parts"]["languages"] == 8 and one_short["limits"] == []
    a_plus = scored(languages_asked=[asked("German", "C1", must_have=False)])
    assert a_plus["parts"]["languages"] == 12 and a_plus["limits"] == []
    assert a_plus["required_languages"] == ["German C1 (a plus)"]
    met = scored(languages_asked=[asked("english", "C1"), asked("Turkish (native)", "C2")])
    assert met["parts"]["languages"] == 15


def test_an_ad_written_in_german_that_names_no_level_is_low_but_not_zero():
    result = scored(ad_language="German", languages_asked=[asked("English", "B2")])
    assert result["parts"]["languages"] == 5 and result["limits"] == []
    assert result["notes"] == [
        "The ad is written in German and doesn't say what level it needs"]
    no_german_needed = scored(ad_language="German",
                              languages_asked=[asked("German", "not_needed")])
    assert no_german_needed["parts"]["languages"] == 15 and no_german_needed["notes"] == []
    unknown_language = scored(ad_language="Dutch")
    assert unknown_language["parts"]["languages"] == 3


def test_a_language_the_cv_does_not_name_is_not_spoken():
    result = scored(languages_asked=[asked("French", "B2")])
    assert result["limits"] == [{"at": 65, "why": "French B2 required, not in your CV"}]
    # Documents that name no language at all can't be compared with the ad.
    assert scored(profile=PROFILE, ad_language="German")["parts"]["languages"] == 15


def test_languages_named_in_the_cvs_own_language_are_recognised():
    # A German CV says "Englisch" and "Deutsch"; scoring names the ad's languages in English.
    german_cv = PROFILE.model_copy(update={"languages": [
        LanguageSkill(language="Englisch", level_as_written="verhandlungssicher", cefr="C1",
                      cefr_is_estimate=True),
        LanguageSkill(language="Deutsch (Muttersprache)", level_as_written="Muttersprache",
                      cefr="native", cefr_is_estimate=False),
    ]})
    result = scored(profile=german_cv, ad_language="German",
                    languages_asked=[asked("English", "B2"), asked("German", "C2")])
    assert result["limits"] == [] and result["parts"]["languages"] == 15
    polish_cv = PROFILE.model_copy(update={"languages": [
        LanguageSkill(language="niemiecki", level_as_written="A2", cefr="A2",
                      cefr_is_estimate=False)]})
    short = scored(profile=polish_cv, languages_asked=[asked("German", "B2")])
    assert short["limits"] == [{"at": 65, "why": "German B2 required, you have A2"}]


def test_the_owners_limits_for_citizenship_doctorate_and_experience():
    blocked = scored(citizenship_or_clearance="required_definitely_out_of_reach",
                     citizenship_or_clearance_words="UK nationals only")
    assert blocked["score"] == 30
    assert blocked["limits"] == [{"at": 30, "why": "UK nationals only: out of reach for you"}]
    unclear = scored(citizenship_or_clearance="required_possible_or_unclear")
    assert unclear["limits"] == []
    assert scored(doctorate="required_person_lacks_it")["score"] == 50
    assert scored(doctorate="required_person_has_it")["limits"] == []
    assert scored(years_required=4)["limits"] == []
    five = scored(years_required=5)
    assert five["score"] == 75 and five["limits"][0]["why"] == (
        "Asks for 5+ years of experience, you have no full-time years yet")
    assert scored(years_required=8)["score"] == 60
    # Years the person already has count: 6 full-time years against 10 asked is 4 short.
    senior = SPEAKER.model_copy(update={"years_full_time_experience": 6.0})
    assert scored(profile=senior, years_required=10)["limits"] == []


def test_the_lowest_limit_wins_and_every_reason_is_kept():
    result = scored(years_required=8, citizenship_or_clearance="required_definitely_out_of_reach",
                    languages_asked=[asked("German", "C1")])
    assert result["score"] == 30
    assert [limit["at"] for limit in result["limits"]] == [30, 60, 65]


def test_a_low_total_is_not_raised_by_a_limit():
    raw = score_json("J1", role=5, years_required=5)
    assert finish(JobScore.model_validate(raw), SPEAKER)["score"] == 5 + 15 + 15 + 15 + 8


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


def test_the_screen_shows_the_same_rubric_parts_as_the_scoring_prompt():
    from pathlib import Path

    import jobcu
    from jobcu.scoring import PARTS

    script = (Path(jobcu.__file__).parent / "web" / "app.js").read_text(encoding="utf-8")
    block = script.split("const SCORE_PARTS = [", 1)[1].split("];", 1)[0]
    shown = dict(re.findall(r'\["(\w+)", "[^"]+", (\d+)\]', block))
    assert {key: int(most) for key, most in shown.items()} == PARTS


def test_the_full_ad_found_online_replaces_what_the_summary_suggested():
    from jobcu.scoring import LanguageAsked, with_ad_read_online

    # A German summary with no level: low for languages, no limit.
    summary = scored(ad_language="German")
    assert summary["parts"]["languages"] == 5 and summary["limits"] == []
    # The full ad online asks for good German and 3 years: now limited, and the card says why.
    online = with_ad_read_online(summary, SPEAKER,
                                 [LanguageAsked(language="German", level="B2", must_have=True)],
                                 years_required=3)
    assert online["score"] == 65 and online["parts"]["languages"] == 0
    assert online["notes"] == [
        "Languages, experience and other requirements read from the full ad online"]
    assert online["evidence"]["years_required"] == 3
    # Or it says English is the working language: the summary's guess goes away.
    english = with_ad_read_online(
        summary, SPEAKER, [LanguageAsked(language="German", level="not_needed", must_have=True)],
        years_required=None)
    assert english["parts"]["languages"] == 15 and english["score"] == summary["score"] + 10


def test_a_citizenship_found_in_the_full_ad_online_limits_the_score():
    # Search 9: Rolls-Royce's two Adzuna summaries scored 85 and 75; its own ads say UK
    # nationals only (30).
    from jobcu.scoring import LanguageAsked, with_ad_read_online

    summary = scored(ad_language="English")
    online = with_ad_read_online(
        summary, SPEAKER, [LanguageAsked(language="English", level="C1", must_have=True)],
        years_required=None, citizenship_or_clearance="required_definitely_out_of_reach",
        citizenship_or_clearance_words="UK nationals only", doctorate="required_person_lacks_it",
        unrelated_key="ignored")
    assert online["score"] == 30
    assert [limit["why"] for limit in online["limits"]] == [
        "UK nationals only: out of reach for you", "A doctorate (PhD) is required"]
    assert "unrelated_key" not in online["evidence"]


def test_the_ad_text_decides_the_job_type_when_the_job_site_leaves_it_open():
    from jobcu.pipeline import job_types_of

    def group_with(types):
        job = FoundJob(source="s", source_job_id="1", url="https://x", title="Engineer",
                       job_types=types)
        return group_duplicates([job], {"s": "job_board"})[0]

    contract = ["fixed_term", "freelance_or_contract", "part_time"]  # Adzuna's "contract"
    assert job_types_of(group_with(contract), {"job_type": "freelance_or_contract"}) == [
        "freelance_or_contract"]
    assert job_types_of(group_with(contract), None) == sorted(contract)
    # One clear type from the site stays; a reading the site contradicts doesn't count.
    assert job_types_of(group_with(["full_time_permanent"]), {"job_type": "part_time"}) == [
        "full_time_permanent"]
    assert job_types_of(group_with(contract), {"job_type": "full_time_permanent"}) == sorted(
        contract)
    assert job_types_of(group_with([]), {"job_type": "part_time"}) == ["part_time"]
    assert job_types_of(group_with([]), {"job_type": None}) == []
