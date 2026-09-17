import pytest
from pydantic import BaseModel

from jobcu.ai.base import (
    AIAuthError,
    AIBadRequest,
    AIInvalidOutput,
    AILimitReached,
    AIOutputTruncated,
    AIRateLimited,
    AIUnavailable,
    ProviderAdapter,
    RawReply,
    Usage,
)
from jobcu.ai.client import AIClient, check_setup
from jobcu.ai.usage import UsageLog
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
    assert adapter.calls[0]["effort"] == "low"
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
    assert adapter.calls[1]["max_output_tokens"] == 2 * adapter.calls[0]["max_output_tokens"]


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
