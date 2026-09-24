import pytest
from pydantic import BaseModel

from jobcu.ai.base import (
    AIAuthError,
    AIBadRequest,
    AIError,
    AIInvalidOutput,
    AILimitReached,
    AIOutputTruncated,
    AIRateLimited,
    AIUnavailable,
    ProviderAdapter,
    RawReply,
    ResearchReply,
    Source,
    Usage,
)
from jobcu.ai.client import THINKING_ROOM, AIClient, check_setup, with_thinking_room
from jobcu.ai.usage import UsageLog, total_tokens
from jobcu.keystore import KeyStore
from jobcu.settings import Settings


class Answer(BaseModel):
    ok: bool
    word: str


class ScriptedAdapter(ProviderAdapter):
    """Plays back a list of replies or errors, and remembers each request."""

    def __init__(self, *script):
        super().__init__("fake-key")
        self.script = list(script)
        self.calls = []

    def complete_json(self, **request):
        self.calls.append(request)
        step = self.script.pop(0)
        if isinstance(step, Exception):
            raise step
        return RawReply(text=step, usage=Usage(input_tokens=10, output_tokens=5))

    def list_models(self):
        return ["model-a"]


GOOD = '{"ok": true, "word": "jobcu"}'


@pytest.fixture(autouse=True)
def forget_model_quirks():
    AIClient._effort_unsupported.clear()


@pytest.fixture
def settings():
    s = Settings()
    s.ai.provider = "gemini"
    s.ai.model = "model-a"
    return s


def make_client(settings, adapter, **kwargs):
    sleeps = []
    client = AIClient(settings, adapter=adapter, sleep=sleeps.append, **kwargs)
    return client, sleeps


def generate(client):
    return client.generate(Answer, step="test", system="s", prompt="p")


def test_answer_is_parsed_and_usage_recorded(settings):
    log = UsageLog()
    client, _ = make_client(settings, ScriptedAdapter(GOOD), usage_log=log, search_id=7)
    assert generate(client) == Answer(ok=True, word="jobcu")
    assert log.for_search(7)["test"].input_tokens == 10


def test_rate_limit_waits_then_continues(settings):
    notes = []
    adapter = ScriptedAdapter(AIRateLimited("limit", retry_after=12), GOOD)
    client, sleeps = make_client(settings, adapter, notify=notes.append)
    assert generate(client).ok
    assert 12 <= sleeps[0] < 14
    assert notes == ["AI limit reached, continuing more slowly."]


def test_impatient_client_reports_rate_limit_instead_of_waiting(settings):
    client, sleeps = make_client(settings, ScriptedAdapter(AIRateLimited("limit")), patient=False)
    with pytest.raises(AIRateLimited):
        generate(client)
    assert sleeps == []


def test_short_outages_are_retried_but_not_forever(settings):
    client, sleeps = make_client(settings, ScriptedAdapter(*[AIUnavailable("down")] * 5))
    with pytest.raises(AIUnavailable):
        generate(client)
    assert len(sleeps) == 4


def test_unsupported_reasoning_setting_is_dropped_and_remembered(settings):
    adapter = ScriptedAdapter(AIBadRequest("no effort"), GOOD, GOOD)
    client, _ = make_client(settings, adapter)
    generate(client)
    assert adapter.calls[0]["effort"] == "medium"  # the default for every step
    assert adapter.calls[1]["effort"] is None
    generate(client)
    assert adapter.calls[2]["effort"] is None


def test_bad_request_without_reasoning_setting_is_reported(settings):
    settings.ai.scoring_effort = None
    client, _ = make_client(settings, ScriptedAdapter(AIBadRequest("bad")))
    with pytest.raises(AIBadRequest):
        generate(client)


def test_wrong_format_is_asked_again_once(settings):
    adapter = ScriptedAdapter('{"ok": "maybe"}', GOOD)
    client, _ = make_client(settings, adapter)
    assert generate(client).ok
    assert "did not follow the required JSON format" in adapter.calls[1]["prompt"]


def test_wrong_format_twice_gives_plain_message(settings):
    client, _ = make_client(settings, ScriptedAdapter("nope", "still nope"))
    with pytest.raises(AIInvalidOutput, match="format Jobcu needs"):
        generate(client)


def test_cut_off_answer_retries_with_more_room(settings):
    adapter = ScriptedAdapter(AIOutputTruncated("cut"), GOOD)
    client, _ = make_client(settings, adapter)
    generate(client)
    room = THINKING_ROOM[settings.ai.scoring_effort]
    first, second = (call["max_output_tokens"] - room for call in adapter.calls)
    assert second == 2 * first  # the answer's own room doubles; thinking keeps its room


def test_thinking_gets_room_on_top_of_the_answer(settings):
    # Medium thinking cut off a 2,000-token answer (2026-09-24): thinking counts as output.
    assert with_thinking_room(2_000, "medium") == 2_000 + THINKING_ROOM["medium"]
    assert with_thinking_room(2_000, None) == 2_000
    assert with_thinking_room(30_000, "high") == 32_000  # within the providers' own limits
    assert with_thinking_room(40_000, "high") == 40_000


def test_monthly_token_limit_stops_ai_work(settings):
    settings.limits.monthly_token_limit = 20
    log = UsageLog()
    client, _ = make_client(settings, ScriptedAdapter(GOOD, GOOD), usage_log=log)
    generate(client)  # uses 15 tokens
    generate(client)  # uses 15 more: now over the limit
    with pytest.raises(AILimitReached):
        generate(client)


def test_reasoning_steps_use_the_second_model_when_set(settings):
    settings.ai.reasoning_model = "model-b"
    adapter = ScriptedAdapter(GOOD, GOOD)
    client, _ = make_client(settings, adapter)
    client.generate(Answer, step="profile", system="s", prompt="p", reasoning=True)
    generate(client)
    assert [c["model"] for c in adapter.calls] == ["model-b", "model-a"]
    assert adapter.calls[0]["effort"] == settings.ai.reasoning_effort


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda s: setattr(s.ai, "provider", None), "choose an AI provider"),
        (lambda s: setattr(s.ai, "model", ""), "choose an AI model"),
    ],
)
def test_missing_setup_gives_plain_messages(settings, change, message):
    change(settings)
    client, _ = make_client(settings, ScriptedAdapter(GOOD))
    with pytest.raises(AIAuthError, match=message):
        generate(client)


def test_missing_key_gives_plain_message(settings):
    with pytest.raises(AIAuthError, match="enter your AI key"):
        AIClient(settings, KeyStore()).generate(Answer, step="t", system="s", prompt="p")


def test_setup_check_reports_success(settings):
    result = check_setup(settings, adapter=ScriptedAdapter(GOOD), sleep=lambda s: None)
    assert result.ok and "Connection works" in result.message


def test_setup_check_reports_wrong_answer(settings):
    reply = '{"ok": false, "word": "hello"}'
    result = check_setup(settings, adapter=ScriptedAdapter(reply), sleep=lambda s: None)
    assert not result.ok and "not correctly" in result.message


def test_setup_check_reports_rejected_key(settings):
    adapter = ScriptedAdapter(AIAuthError("The AI provider didn't accept the key."))
    result = check_setup(settings, adapter=adapter, sleep=lambda s: None)
    assert not result.ok and "didn't accept the key" in result.message


def test_setup_check_doesnt_wait_on_rate_limits(settings):
    adapter = ScriptedAdapter(AIRateLimited("limit", retry_after=60))
    result = check_setup(settings, adapter=adapter, sleep=lambda s: pytest.fail("waited"))
    assert not result.ok and "Wait a minute" in result.message


# --- Looking things up on the web -----------------------------------------------------


class SearchingAdapter(ProviderAdapter):
    """A provider that can search the web, for tests."""

    can_search_the_web = True

    def __init__(self, reply=None):
        super().__init__("fake-key")
        self.calls = []
        self.reply = reply

    def complete_json(self, **request):
        raise AssertionError("not used here")

    def research(self, **request):
        self.calls.append(request)
        return self.reply or ResearchReply(
            "Dresden is above the national average.",
            [Source("https://example.test/results", "Election results")],
            Usage(input_tokens=500, output_tokens=200, web_searches=3),
        )

    def list_models(self):
        return []


def research_settings():
    settings = Settings()
    settings.ai.provider = "openai"
    settings.ai.model = "everyday-model"
    return settings


def test_web_research_counts_searches_and_keeps_the_sources():
    adapter = SearchingAdapter()
    client = AIClient(research_settings(), adapter=adapter, usage_log=UsageLog())
    reply = client.research(step="location", system="Rules", prompt="Which cities?")
    assert [source.url for source in reply.sources] == ["https://example.test/results"]
    assert client.web_searches_used == 3
    assert adapter.calls[0]["max_searches"] == 4
    assert total_tokens(UsageLog().this_month()) == 700


def test_web_research_stops_at_the_cap_and_when_switched_off():
    settings = research_settings()
    settings.limits.web_search_cap = 2
    client = AIClient(settings, adapter=SearchingAdapter(), usage_log=UsageLog())
    client.research(step="location", system="Rules", prompt="Which cities?")
    with pytest.raises(AILimitReached):
        client.research(step="location", system="Rules", prompt="And which towns?")
    # A yes for 5 more jobs' look-ups allows exactly those, on top of what was left.
    client.allow_more_web_searches(5)
    assert client.web_searches_left() == 5
    client.allow_more_web_searches()
    assert client.web_searches_left() == 7  # another allowance as big as the one in Settings

    settings = research_settings()
    settings.use_web_search = False
    with pytest.raises(AIError):
        AIClient(settings, adapter=SearchingAdapter()).research(
            step="location", system="Rules", prompt="Which cities?")


def test_a_provider_that_cannot_search_says_so_plainly():
    class Plain(SearchingAdapter):
        can_search_the_web = False

    client = AIClient(research_settings(), adapter=Plain())
    with pytest.raises(AIError) as problem:
        client.research(step="location", system="Rules", prompt="Which cities?")
    assert "can't look things up on the web" in problem.value.message


def test_web_research_asks_again_without_a_thinking_setting_the_model_refuses():
    class NoEffort(SearchingAdapter):
        def research(self, **request):
            if request.get("effort"):
                self.calls.append(request)
                raise AIBadRequest("reasoning isn't supported", "400")
            return super().research(**request)

    adapter = NoEffort()
    client = AIClient(research_settings(), adapter=adapter, usage_log=UsageLog())
    client.research(step="job_places", system="Rules", prompt="Find it")
    # The person's reasoning setting (medium by default), then without it.
    assert [call.get("effort") for call in adapter.calls] == ["medium", None]
    # Remembered: the next look-up doesn't try the setting again.
    client.research(step="job_places", system="Rules", prompt="Find it", effort="low")
    assert [call.get("effort") for call in adapter.calls] == ["medium", None, None]
