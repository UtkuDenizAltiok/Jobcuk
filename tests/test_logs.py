import logging

from jobcu.logs import RedactKeys


def test_key_like_values_are_hidden_in_logs():
    fake_key = "sk-" + "proj-" + "Ab12" * 8
    record = logging.LogRecord("x", logging.INFO, __file__, 1, "failed with %s", (fake_key,), None)
    RedactKeys().filter(record)
    assert fake_key not in record.getMessage()
    assert "[hidden]" in record.getMessage()
