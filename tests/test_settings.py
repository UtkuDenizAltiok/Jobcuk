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
