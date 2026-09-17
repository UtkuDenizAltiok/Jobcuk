from jobcu import db


def test_database_is_created_and_up_to_date(temporary_data_dir):
    with db.connect() as conn:
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master")}
    assert version == len(db.MIGRATIONS)
    assert "ai_usage" in tables
    assert (temporary_data_dir / db.DB_FILENAME).exists()


def test_connecting_again_keeps_data():
    with db.connect() as conn:
        conn.execute(
            "INSERT INTO ai_usage (step, provider, model, input_tokens, output_tokens, "
            "cached_input_tokens, reasoning_tokens, web_searches) VALUES ('t','p','m',1,2,0,0,0)"
        )
    with db.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM ai_usage").fetchone()[0] == 1


def test_many_parts_of_jobcu_can_open_a_new_database_at_once():
    import threading

    errors = []

    def open_database():
        try:
            with db.connect() as conn:
                conn.execute("SELECT COUNT(*) FROM jobs").fetchone()
        except Exception as exc:  # collected so the test can show them
            errors.append(exc)

    threads = [threading.Thread(target=open_database) for _ in range(12)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert errors == []
