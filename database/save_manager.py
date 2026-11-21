"""SQLite persistence for the profile and queryable local run analytics."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path


SAVE_DIR = Path.home() / "AppData" / "Local" / "Afterhours1999"
SAVE_DIR.mkdir(parents=True, exist_ok=True)
SAVE_PATH = SAVE_DIR / "afterhours.sqlite3"

RUN_FIELDS = (
    "elapsed", "distance", "score", "coins", "lane_changes", "lane_change_threats",
    "lane_change_successes", "jumps", "slides",
    "jump_successes", "slide_successes", "dash_activations", "dash_clears",
    "near_misses", "collision_count", "successful_avoids", "powerup_count",
    "average_reaction", "consistency", "difficulty_factor", "difficulty_preference",
)
TEXT_RUN_FIELDS = frozenset(("difficulty_preference",))
REAL_RUN_FIELDS = frozenset(("elapsed", "average_reaction", "consistency", "difficulty_factor"))
INTEGER_RUN_FIELDS = frozenset(RUN_FIELDS) - TEXT_RUN_FIELDS - REAL_RUN_FIELDS
JSON_RUN_FIELDS = ("collisions", "powerups", "reaction_samples")


class SaveManager:
    """Preserve the existing profile API while keeping analytics in SQL tables.

    Version 4 saves placed run history inside the profile JSON. On first load,
    this manager migrates that payload atomically and thereafter returns the
    same ``analytics`` mapping assembled from the SQLite analytics tables.
    """

    def __init__(self, path: Path = SAVE_PATH) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path)
        self.connection.execute(
            "CREATE TABLE IF NOT EXISTS save (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
        )
        self.connection.execute(
            "CREATE TABLE IF NOT EXISTS analytics_totals "
            "(metric TEXT PRIMARY KEY, value INTEGER NOT NULL)"
        )
        self.connection.execute(
            "CREATE TABLE IF NOT EXISTS analytics_meta "
            "(key TEXT PRIMARY KEY, value TEXT NOT NULL)"
        )
        run_columns = ", ".join(
            f'"{field}" ' + ("TEXT" if field in TEXT_RUN_FIELDS else
                               "REAL" if field in REAL_RUN_FIELDS else "INTEGER")
            for field in RUN_FIELDS
        )
        json_columns = ", ".join(f'"{field}" TEXT NOT NULL' for field in JSON_RUN_FIELDS)
        self.connection.execute(
            f"CREATE TABLE IF NOT EXISTS run_summaries "
            f"(run_index INTEGER PRIMARY KEY, {run_columns}, {json_columns})"
        )
        existing_columns = {row[1] for row in self.connection.execute(
            "PRAGMA table_info(run_summaries)"
        )}
        # Additive columns keep databases created by an earlier incremental
        # build readable without replacing existing run history.
        for field in RUN_FIELDS + JSON_RUN_FIELDS:
            if field not in existing_columns:
                kind = ("TEXT" if field in TEXT_RUN_FIELDS or field in JSON_RUN_FIELDS else
                        "REAL" if field in REAL_RUN_FIELDS else "INTEGER")
                self.connection.execute(f'ALTER TABLE run_summaries ADD COLUMN "{field}" {kind}')
        self.connection.commit()

    def _store_analytics(self, analytics: object) -> None:
        if not isinstance(analytics, dict):
            return
        totals = analytics.get("totals")
        totals = totals if isinstance(totals, dict) else {}
        try:
            preferred_lane = max(0, min(2, int(analytics.get("preferred_lane", 1))))
        except (TypeError, ValueError, OverflowError):
            preferred_lane = 1
        lane_counts = analytics.get("lane_counts")
        metrics: dict[str, int] = {}
        for key in ("runs", "distance", "coins", "collisions", "dash_clears", "near_misses"):
            try:
                metrics[key] = max(0, min(2_147_483_647, int(totals.get(key, 0))))
            except (TypeError, ValueError, OverflowError):
                metrics[key] = 0
        metrics["preferred_lane"] = preferred_lane
        for lane in range(3):
            try:
                metrics[f"lane_count_{lane}"] = max(0, min(2_147_483_647, int(lane_counts[lane])))
            except (TypeError, ValueError, OverflowError, IndexError):
                metrics[f"lane_count_{lane}"] = 0

        runs = analytics.get("runs")
        runs = [item for item in runs if isinstance(item, dict)][-100:] if isinstance(runs, list) else []
        fields_sql = ", ".join(f'"{field}"' for field in RUN_FIELDS + JSON_RUN_FIELDS)
        placeholders = ", ".join("?" for _ in range(1 + len(RUN_FIELDS) + len(JSON_RUN_FIELDS)))
        insert_run = f"INSERT INTO run_summaries(run_index, {fields_sql}) VALUES({placeholders})"

        self.connection.execute("DELETE FROM analytics_totals")
        self.connection.executemany(
            "INSERT INTO analytics_totals(metric, value) VALUES(?, ?)", metrics.items()
        )
        self.connection.execute("DELETE FROM run_summaries")
        rows = []
        for index, run in enumerate(runs):
            values = []
            for field in RUN_FIELDS:
                value = run.get(field)
                if field in INTEGER_RUN_FIELDS:
                    try:
                        value = max(0, min(2_147_483_647, int(value or 0)))
                    except (TypeError, ValueError, OverflowError):
                        value = 0
                elif field in TEXT_RUN_FIELDS:
                    value = value if isinstance(value, str) else None
                else:
                    try:
                        value = float(value) if value is not None else None
                    except (TypeError, ValueError, OverflowError):
                        value = None
                values.append(value)
            rows.append((index, *values,
                         *(json.dumps(run.get(field, {} if field != "reaction_samples" else []),
                                       allow_nan=False) for field in JSON_RUN_FIELDS)))
        if rows:
            self.connection.executemany(insert_run, rows)
        self.connection.execute(
            "INSERT INTO analytics_meta(key, value) VALUES('initialized', '1') "
            "ON CONFLICT(key) DO UPDATE SET value='1'"
        )

    def _read_analytics(self) -> dict | None:
        marker = self.connection.execute(
            "SELECT value FROM analytics_meta WHERE key='initialized'"
        ).fetchone()
        if marker is None:
            return None
        totals = {key: int(value) for key, value in self.connection.execute(
            "SELECT metric, value FROM analytics_totals"
        )}
        lane_counts = [totals.pop(f"lane_count_{lane}", 0) for lane in range(3)]
        preferred_lane = totals.pop("preferred_lane", 1)
        for key in ("runs", "distance", "coins", "collisions", "dash_clears", "near_misses"):
            totals.setdefault(key, 0)
        rows = self.connection.execute(
            "SELECT " + ", ".join(f'"{field}"' for field in RUN_FIELDS + JSON_RUN_FIELDS)
            + " FROM run_summaries ORDER BY run_index"
        ).fetchall()
        runs = []
        for row in rows:
            run = dict(zip(RUN_FIELDS + JSON_RUN_FIELDS, row))
            for field in JSON_RUN_FIELDS:
                try:
                    run[field] = json.loads(run[field])
                except (json.JSONDecodeError, TypeError):
                    run[field] = [] if field == "reaction_samples" else {}
            runs.append(run)
        return {"runs": runs, "totals": totals,
                "preferred_lane": preferred_lane, "lane_counts": lane_counts}

    def save(self, state: dict) -> None:
        state = dict(state)
        analytics = state.pop("analytics", None)
        payload = json.dumps(state, allow_nan=False)
        # Profile and analytics are committed together so a crash cannot leave
        # the save payload and normalized run history at different versions.
        with self.connection:
            self.connection.execute(
                "INSERT INTO save(key, value) VALUES('game', ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (payload,),
            )
            if analytics is not None:
                self._store_analytics(analytics)

    def load(self) -> dict | None:
        row = self.connection.execute(
            "SELECT value FROM save WHERE key='game'"
        ).fetchone()
        if row is None:
            return None
        try:
            value = json.loads(row[0])
        except (json.JSONDecodeError, TypeError):
            return None
        if not isinstance(value, dict):
            return None

        stored_analytics = self._read_analytics()
        if stored_analytics is None and isinstance(value.get("analytics"), dict):
            # Migrate the original JSON analytics payload without losing the
            # caller-visible state or unknown legacy profile fields.
            stored_analytics = value["analytics"]
            clean_profile = dict(value)
            clean_profile.pop("analytics", None)
            with self.connection:
                self._store_analytics(stored_analytics)
                self.connection.execute(
                    "UPDATE save SET value=? WHERE key='game'",
                    (json.dumps(clean_profile, allow_nan=False),),
                )
        if stored_analytics is not None:
            value["analytics"] = stored_analytics
        return value

    def exists(self) -> bool:
        return self.load() is not None

    def close(self) -> None:
        self.connection.close()
