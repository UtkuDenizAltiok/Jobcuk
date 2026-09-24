import json

from jobcu.settings import Settings, load_settings, save_settings, settings_path


def test_defaults_when_nothing_saved():
    settings = load_settings()
    assert settings.ai.provider is None
    assert settings.limits.scoring_cap > 0


def test_saved_settings_come_back():
    settings = Settings()
    settings.ai.provider = "gemini"
    settings.ai.model = "some-model"
    save_settings(settings)
    assert load_settings().ai.model == "some-model"


def test_damaged_settings_file_is_set_aside():
    path = settings_path()
    path.write_text("{broken", encoding="utf-8")
    assert load_settings() == Settings()
    assert path.with_name(path.name + ".damaged").exists()


def test_older_settings_move_from_low_to_medium_thinking_once(temporary_data_dir):
    # The owner's choice (2026-09-24): medium everywhere. "low" was the old default nobody
    # could change on screen.
    old = {"ai": {"provider": "gemini", "model": "m", "scoring_effort": "low",
                  "reasoning_effort": "medium"}}
    temporary_data_dir.mkdir(parents=True, exist_ok=True)
    settings_path().write_text(json.dumps(old), encoding="utf-8")
    settings = load_settings()
    assert settings.ai.scoring_effort == "medium" and settings.version == 2
    # From version 2 on, what is saved stays as saved.
    settings.ai.scoring_effort = "low"
    save_settings(settings)
    assert load_settings().ai.scoring_effort == "low"
    assert Settings().ai.scoring_effort == "medium"
