import pytest

from jobcu.paths import DATA_DIR_ENV


@pytest.fixture(autouse=True)
def temporary_data_dir(tmp_path, monkeypatch):
    """Every test uses a throwaway data folder, never the real one."""
    folder = tmp_path / "jobcu-data"
    monkeypatch.setenv(DATA_DIR_ENV, str(folder))
    return folder
