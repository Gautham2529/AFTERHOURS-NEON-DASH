import json

from database.save_manager import SaveManager


def test_save_round_trip(tmp_path):
    save = SaveManager(tmp_path / "test.sqlite3")
    state = {"money": 42, "inventory": [
        "camera"], "city_memory": {"met_iko": True}}
    save.save(state)
    assert save.load() == state
    save.close()


def test_missing_save(tmp_path):
    save = SaveManager(tmp_path / "missing.sqlite3")
    assert save.load() is None
    save.close()


def test_corrupted_or_non_object_save_is_treated_as_missing(tmp_path):
    save = SaveManager(tmp_path / "corrupt.sqlite3")
    for payload in ("{broken", "[1, 2, 3]"):
        save.connection.execute(
            "INSERT INTO save(key, value) VALUES('game', ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (payload,),
        )
        save.connection.commit()
        assert save.load() is None
    save.close()


def test_run_analytics_are_normalized_in_sqlite_and_survive_legacy_migration(tmp_path):
    path = tmp_path / "analytics.sqlite3"
    save = SaveManager(path)
    legacy = {"money": 7, "analytics": {
        "runs": [{"distance": 123, "score": 456,
                   "difficulty_factor": 1.07, "difficulty_preference": "challenge"}],
        "totals": {"runs": 1, "distance": 123},
        "preferred_lane": 2, "lane_counts": [0, 0, 1],
    }}
    save.connection.execute(
        "INSERT INTO save(key, value) VALUES('game', ?) ",
        (json.dumps(legacy),),
    )
    save.connection.commit()

    assert save.load() == legacy
    assert save.connection.execute("SELECT COUNT(*) FROM run_summaries").fetchone()[0] == 1
    difficulty_history = save.connection.execute(
        "SELECT difficulty_factor, difficulty_preference FROM run_summaries"
    ).fetchone()
    assert difficulty_history == (1.07, "challenge")
    profile_payload = save.connection.execute(
        "SELECT value FROM save WHERE key='game'"
    ).fetchone()[0]
    assert "analytics" not in json.loads(profile_payload)

    # Future writes keep the legacy-facing load contract while persisting rows.
    updated = {"money": 9, "analytics": {
        "runs": [{"distance": 300, "score": 900,
                   "difficulty_factor": 1.07, "difficulty_preference": "challenge"}],
        "totals": {"runs": 2, "distance": 423},
        "preferred_lane": 1, "lane_counts": [0, 1, 1],
    }}
    save.save(updated)
    loaded = save.load()
    assert loaded["money"] == 9
    assert loaded["analytics"]["runs"][0]["distance"] == 300
    assert loaded["analytics"]["totals"]["distance"] == 423
    assert save.connection.execute("SELECT COUNT(*) FROM run_summaries").fetchone()[0] == 1
    save.close()

    reopened = SaveManager(path)
    persisted = reopened.load()
    assert persisted["money"] == 9
    assert persisted["analytics"]["runs"][0]["difficulty_factor"] == 1.07
    assert persisted["analytics"]["runs"][0]["difficulty_preference"] == "challenge"
    assert persisted["analytics"]["totals"]["distance"] == 423
    reopened.close()
