import os
import sys
from pathlib import Path

import pytest

from jobcu import paths


def test_data_dir_can_be_overridden(temporary_data_dir):
    assert paths.data_dir() == temporary_data_dir.resolve()


def test_default_data_dir_is_the_standard_place_for_app_data(monkeypatch):
    monkeypatch.delenv(paths.DATA_DIR_ENV)
    folder = paths.data_dir()
    home = Path.home()
    if sys.platform == "darwin":
        assert folder == home / "Library" / "Application Support" / "Jobcu"
    elif sys.platform == "win32":
        assert folder.parts[-3:] == ("AppData", "Local", "Jobcu")
    assert folder.name == "Jobcu"


def test_default_data_dir_is_outside_the_code_folder(monkeypatch):
    monkeypatch.delenv(paths.DATA_DIR_ENV)
    project_root = Path(paths.__file__).resolve().parents[2]
    assert not paths.data_dir().is_relative_to(project_root)


def test_ensure_data_dir_creates_folder_with_explanation(temporary_data_dir):
    assert not temporary_data_dir.exists()
    folder = paths.ensure_data_dir()
    assert folder.is_dir()
    assert "never uploaded" in (folder / "README.txt").read_text(encoding="utf-8")


@pytest.mark.skipif(os.name != "posix", reason="Unix permissions")
def test_data_dir_is_private_to_the_user():
    folder = paths.ensure_data_dir()
    assert folder.stat().st_mode & 0o777 == 0o700
