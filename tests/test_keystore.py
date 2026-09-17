import os

import pytest

from jobcu.keystore import KEYS_FILENAME, KeyStore, KeyStoreError, mask

FAKE_KEY = "fake-" + "x" * 24


def test_keys_are_saved_in_the_data_folder(temporary_data_dir):
    store = KeyStore()
    store.set("adzuna_app_key", FAKE_KEY)
    assert store.path == temporary_data_dir.resolve() / KEYS_FILENAME
    assert KeyStore().get("adzuna_app_key") == FAKE_KEY


def test_set_get_has_names_delete():
    store = KeyStore()
    assert store.get("reed") is None
    assert not store.has("reed")
    store.set("reed", f"  {FAKE_KEY}\n")
    assert store.get("reed") == FAKE_KEY
    assert store.has("reed")
    assert store.names() == ["reed"]
    store.delete("reed")
    assert store.get("reed") is None
    store.delete("reed")  # deleting twice is fine


def test_empty_key_is_refused():
    with pytest.raises(KeyStoreError):
        KeyStore().set("reed", "   ")


@pytest.mark.skipif(os.name != "posix", reason="Unix permissions")
def test_keys_file_is_readable_only_by_the_user():
    store = KeyStore()
    store.set("reed", FAKE_KEY)
    assert store.path.stat().st_mode & 0o777 == 0o600


def test_damaged_keys_file_gives_plain_message_and_can_be_replaced():
    store = KeyStore()
    store.set("reed", FAKE_KEY)
    store.path.write_text("{not valid", encoding="utf-8")
    with pytest.raises(KeyStoreError, match="enter them again"):
        store.get("reed")
    store.set("reed", FAKE_KEY)
    assert store.get("reed") == FAKE_KEY
    assert store.path.with_name(KEYS_FILENAME + ".damaged").exists()


def test_mask_shows_only_the_end():
    assert mask("abcdefghijkl3f9a") == "••••3f9a"
    assert mask("short") == "••••"
