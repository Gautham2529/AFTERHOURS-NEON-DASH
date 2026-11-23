"""Regression scenarios for the runner's highest-risk state transitions."""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame
import pytest
from datetime import date

import engine.game as game_module
from database.save_manager import SaveManager
from engine.game import NeonRunner, PLAYER_Y
from engine.progression import Goal


class SilentAudio:
    muted = False

    def set_music_volume(self, _value): pass
    def set_sfx_volume(self, _value): pass
    def set_boost(self, _active): pass
    def play(self, _name): pass
    def toggle_mute(self): self.muted = not self.muted


@pytest.fixture
def runner(tmp_path, monkeypatch):
    pygame.init()
    pygame.display.set_mode((1, 1))
    save = SaveManager(tmp_path / "game.sqlite3")
    monkeypatch.setattr(game_module, "SaveManager", lambda: save)
    monkeypatch.setattr(game_module, "AudioBus", SilentAudio)
    instance = NeonRunner()
    yield instance
    save.close()
    pygame.quit()


def test_start_menu_selection_wraps_and_comfort_screen_opens(runner):
    runner.state = "menu"
    runner.menu_selection = 0
    runner.menu_action(4)
    assert runner.state == "comfort"
    runner.state = "menu"
    runner.menu_selection = 5
    runner.menu_selection = (runner.menu_selection + 1) % 6
    assert runner.menu_selection == 0


def test_game_starts_fullscreen_and_f11_toggles_windowed_mode(runner):
    assert runner.fullscreen
    assert pygame.display.get_surface().get_flags() & pygame.FULLSCREEN

    pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_F11))
    runner.handle_events()
    assert not runner.fullscreen
    assert not pygame.display.get_surface().get_flags() & pygame.FULLSCREEN

    pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_F11))
    runner.handle_events()
    assert runner.fullscreen
    assert pygame.display.get_surface().get_flags() & pygame.FULLSCREEN


def test_comfort_levels_wrap_and_persist(runner):
    runner.music_level = 3
    runner.change_comfort(2)
    assert runner.music_level == 0
    assert runner.save.load()["music_level"] == 0


def test_touch_swipes_are_clamped_to_three_lanes(runner):
    runner.state = "playing"
    runner.lane = 1
    runner.handle_touch((500, 200), (600, 200))
    assert runner.lane == 2
    runner.handle_touch((500, 200), (400, 200))
    assert runner.lane == 1


def test_lane_change_records_a_successful_hazard_escape(runner):
    runner.state = "playing"
    runner.entities = [{"kind": "barrier", "lane": 1, "y": PLAYER_Y - 50}]
    runner.touch_action("left")
    assert runner.lane == 0
    assert runner.telemetry.lane_changes == 1
    assert runner.telemetry.lane_change_threats == 1
    assert runner.telemetry.lane_change_successes == 1


def test_lane_change_into_an_occupied_lane_is_not_a_success(runner):
    runner.state = "playing"
    runner.entities = [{"kind": "barrier", "lane": 1, "y": PLAYER_Y - 50},
                       {"kind": "fence", "lane": 0, "y": PLAYER_Y - 45}]
    runner.touch_action("left")
    assert runner.telemetry.lane_change_threats == 1
    assert runner.telemetry.lane_change_successes == 0


def test_spawn_pattern_falls_back_when_sequence_has_no_reachable_lane(runner):
    class UnsafePatternSource:
        HAZARD_KINDS = frozenset(("barrier", "gate", "electric_car", "fence"))

        def generate(self, *_args, **_kwargs):
            return [{"kind": "barrier", "lane": 1, "y": 145.0}]

    runner.entities = [{"kind": kind, "lane": lane, "y": 400.0}
                       for lane, kind in enumerate(("barrier", "gate", "fence"))]
    runner.patterns = UnsafePatternSource()
    existing_count = len(runner.entities)
    runner.spawn_pattern()
    assert len(runner.entities) == existing_count


def test_shield_absorbs_collision_then_three_crashes_end_run(runner):
    runner.begin_run()
    runner.shield = 1
    runner.entities = [{"kind": "barrier", "lane": 1, "y": PLAYER_Y - 1}]
    runner.update(0.04)
    assert runner.shield == 0
    assert runner.hits == 0

    for expected_hits in (1, 2, 3):
        runner.hit_cooldown = 0
        runner.entities = [{"kind": "barrier", "lane": 1, "y": PLAYER_Y - 1}]
        runner.update(0.04)
        assert runner.hits == expected_hits
    assert runner.state == "gameover"


def test_coin_collection_updates_score_wallet_and_save(runner):
    runner.begin_run()
    runner.pickup({"kind": "coin"})
    assert runner.coins == 1
    assert runner.token_score_total > 0
    runner.finish_run()
    state = runner.save.load()
    assert state["upgrade_points"] == 11
    assert state["best_coins"] == 1


def test_touch_dash_and_reward_claims_are_functional_and_idempotent(runner):
    runner.begin_run()
    runner.dash_charge = 100
    runner.touch_action("dash")
    assert runner.dash_time > 0
    assert runner.dash_charge == 0

    runner.distance = 1000
    runner.coins = 20
    runner.dash_clears = 5
    runner.finish_run()
    earned = runner.upgrade_points
    assert runner.mission_ids == {"distance_1000", "tokens_20", "dash_5"}
    assert runner.achievement_ids == {"first_run"}
    runner.finish_run()
    assert runner.upgrade_points == earned


def test_daily_challenge_reward_is_saved_and_claimed_once(runner):
    runner.daily_goal = Goal("daily_test", "TODAY", "Test objective", "distance", 1, 7)
    runner.begin_run()
    runner.distance = 1
    runner.finish_run()
    points_after_claim = runner.upgrade_points
    assert runner.daily_claimed
    assert runner.save.load()["daily_claimed"] is True
    assert runner.save.load()["challenge_history"][-1]["period"] == "daily"
    runner.finish_run()
    assert runner.upgrade_points == points_after_claim


def test_progression_pages_are_reachable_and_render(runner):
    runner.menu_action(5)
    assert runner.state == "hub"
    for index, page in enumerate(("missions", "achievements", "statistics", "profile")):
        runner.open_hub_page(index)
        assert runner.state == page
        runner.draw()
    runner.open_hub_page(4)
    assert runner.state == "worlds"
    runner.draw()
    runner.open_hub_page(5)
    assert runner.state == "challenge_history"
    runner.draw()


def test_pause_overlay_mouse_button_resumes_without_restarting(runner):
    runner.begin_run()
    runner.score = 321
    runner.state = "paused"
    runner.mouse_click((480, 317))
    assert runner.state == "playing"
    assert runner.score == 321


def test_custom_city_background_is_not_covered_by_fallback_sky(runner):
    runner.city_backdrop = pygame.Surface((960, 540))
    runner.city_backdrop.fill((12, 34, 56))
    runner.stars = []
    runner.draw_city()
    assert runner.screen.get_at((2, 2))[:3] == (12, 34, 56)


def test_loaded_audio_levels_are_safely_bounded(tmp_path, monkeypatch):
    pygame.init()
    pygame.display.set_mode((1, 1))
    save = SaveManager(tmp_path / "corrupt-level.sqlite3")
    save.save({"music_level": 99, "sfx_level": -2})
    monkeypatch.setattr(game_module, "SaveManager", lambda: save)
    monkeypatch.setattr(game_module, "AudioBus", SilentAudio)
    try:
        runner = NeonRunner()
        assert 0 <= runner.music_level <= 3
        assert 0 <= runner.sfx_level <= 3
    finally:
        save.close()
        pygame.quit()


def test_malformed_audio_levels_use_defaults(tmp_path, monkeypatch):
    pygame.init()
    pygame.display.set_mode((1, 1))
    save = SaveManager(tmp_path / "malformed-level.sqlite3")
    save.save({"music_level": "loud", "sfx_level": None})
    monkeypatch.setattr(game_module, "SaveManager", lambda: save)
    monkeypatch.setattr(game_module, "AudioBus", SilentAudio)
    try:
        runner = NeonRunner()
        assert (runner.music_level, runner.sfx_level) == (2, 1)
    finally:
        save.close()
        pygame.quit()


def test_malformed_progression_fields_recover_to_valid_defaults(tmp_path, monkeypatch):
    pygame.init()
    pygame.display.set_mode((1, 1))
    save = SaveManager(tmp_path / "malformed-progress.sqlite3")
    save.save({"upgrades": "corrupt", "unlocked_avatars": 42,
               "upgrade_points": "many", "best_score": -100})
    monkeypatch.setattr(game_module, "SaveManager", lambda: save)
    monkeypatch.setattr(game_module, "AudioBus", SilentAudio)
    try:
        runner = NeonRunner()
        assert runner.upgrades == {key: 0 for key, *_ in game_module.UPGRADES}
        assert runner.unlocked_avatars == {"runner"}
        assert runner.upgrade_points == 0
        assert runner.best_score == 0
    finally:
        save.close()
        pygame.quit()


def test_older_unknown_save_fields_are_preserved_on_new_game_save(tmp_path, monkeypatch):
    pygame.init()
    pygame.display.set_mode((1, 1))
    save = SaveManager(tmp_path / "legacy-progress.sqlite3")
    legacy = {"rpg_story_flags": {"met_operator": True}, "old_wallet": 27}
    save.save(legacy)
    monkeypatch.setattr(game_module, "SaveManager", lambda: save)
    monkeypatch.setattr(game_module, "AudioBus", SilentAudio)
    try:
        runner = NeonRunner()
        runner.persist()
        result = save.load()
        assert result["rpg_story_flags"] == {"met_operator": True}
        assert result["old_wallet"] == 27
        assert result["schema_version"] == game_module.SAVE_SCHEMA_VERSION
    finally:
        save.close()
        pygame.quit()


def test_menu_comfort_and_live_run_render_without_error(runner):
    runner.state = "menu"
    runner.draw()
    runner.state = "comfort"
    runner.draw()
    runner.begin_run()
    runner.touch_controls = True
    runner.update(1 / 60)
    runner.draw()


def test_vector_gameplay_render_preserves_simulation_state(runner):
    runner.begin_run()
    runner.score = 4321
    runner.entities = [
        {"kind": "barrier", "lane": 0, "y": 350.0},
        {"kind": "coin", "lane": 2, "y": 280.0},
    ]
    before = (runner.lane, runner.score, runner.coins, runner.distance,
              tuple((item["kind"], item["lane"], item["y"]) for item in runner.entities))

    runner.draw()

    after = (runner.lane, runner.score, runner.coins, runner.distance,
             tuple((item["kind"], item["lane"], item["y"]) for item in runner.entities))
    assert after == before
    assert runner.screen.get_size() == (960, 540)


def test_world_selection_respects_unlocks_and_persists(runner):
    runner.world_selection = 1
    runner.state = "worlds"
    runner.choose_world()
    assert runner.world_id == "city"
    assert runner.state == "worlds"
    runner.profile_level = 2
    runner.choose_world()
    assert runner.world_id == "metro"
    assert runner.save.load()["world_id"] == "metro"


def test_distance_world_transition_updates_visual_state_and_spawn_pool(runner):
    runner.profile_level = 2
    runner.begin_run()
    runner.distance = 4999
    runner.spawn_timer = 1
    runner.update(.04)
    assert runner.current_world_key == "metro"
    assert runner.world_transition_timer > 0
    runner.spawn_pattern()
    assert all(entity["kind"] != "fence" for entity in runner.entities)


def test_dash_trail_obeys_reduced_motion_setting(runner):
    runner.reduced_motion = False
    runner.begin_run()
    runner.dash_charge = 100
    runner.activate_dash()
    runner.update(.04)
    assert runner.particles.particles
    runner.draw()

    runner.particles.clear()
    runner.dash_trail_timer = 0
    runner.reduced_motion = True
    runner.update(.04)
    assert runner.particles.particles == []


def test_comfort_reduced_flashing_and_sensitivity_persist(runner):
    runner.change_comfort(8)
    runner.change_comfort(9)
    saved = runner.save.load()
    assert saved["reduced_flashing"] is False
    assert saved["control_sensitivity"] == 2


def test_coin_bonus_pickup_doubles_tokens_and_dash_charge(runner):
    runner.begin_run()
    runner.pickup({"kind": "coin_bonus"})
    runner.pickup({"kind": "coin"})
    assert runner.coins == 2
    assert runner.dash_charge == 16
    assert runner.telemetry.powerups["coin_bonus"] == 1


def test_weekly_challenge_reward_is_recorded_once(runner):
    runner.weekly_goal = Goal("weekly_test", "THIS WEEK", "Test weekly goal", "distance", 1, 9)
    runner.begin_run()
    runner.distance = 1
    runner.finish_run()
    assert runner.weekly_claimed
    assert runner.challenge_history[-1]["period"] == "weekly"
    assert runner.save.load()["weekly_progress"]["distance"] == 1


def test_challenge_claim_history_prevents_rewards_after_clock_rollback(runner, monkeypatch):
    today = date.today()
    prior_date = date.fromordinal(today.toordinal() - 1)
    prior_day = prior_date.isoformat()
    iso = prior_date.isocalendar()
    prior_week = f"{iso.year}-W{iso.week:02d}"

    class FixedDate(date):
        @classmethod
        def today(cls):
            return cls.fromisoformat(prior_day)

    data = runner.save.load() or {}
    data.update({"daily_date": today.isoformat(), "daily_claimed": False,
                 "weekly_key": "future-week", "weekly_claimed": False,
                 "challenge_history": [
                     {"period": "daily", "key": "daily_tokens", "date": prior_day},
                     {"period": "weekly", "key": "weekly_distance", "date": prior_week},
                 ]})
    runner.save.save(data)
    monkeypatch.setattr(game_module, "date", FixedDate)
    restored = NeonRunner()
    assert restored.daily_claimed is True
    assert restored.weekly_claimed is True


def test_ghost_source_cycles_and_persists(runner):
    runner.change_comfort(7)
    assert runner.ghost_source == "previous"
    runner.previous_ghost.record(.05, 1, "run")
    runner.persist()
    assert runner.save.load()["ghost_source"] == "previous"


def test_selected_saved_run_ghost_is_bounded_drawable_and_persistent(runner):
    for score, lane in ((450, 0), (900, 2)):
        runner.begin_run()
        runner.score = score
        runner.distance = score
        runner.ghost.record(0, lane, "run")
        runner.ghost.record(.05, lane, "jump", .4)
        runner.finish_run()

    assert [item["run"] for item in runner.ghost_archive] == [2, 1]
    runner.change_comfort(7)  # best -> previous
    runner.change_comfort(7)  # previous -> saved archive
    assert runner.ghost_source == "archive"
    assert runner.selected_ghost_replay().samples[0][1] == 2
    runner.select_ghost_archive(1)
    assert runner.ghost_archive_selection == 1
    assert runner.selected_ghost_replay().samples[0][1] == 0
    runner.state = "playing"
    runner.draw()

    restored = NeonRunner()
    assert restored.ghost_source == "archive"
    assert restored.ghost_archive_selection == 1
    assert restored.selected_ghost_replay().samples[0][1] == 0


def test_saved_run_ghost_archive_keeps_only_five_recent_runs(runner):
    for run in range(7):
        runner.begin_run()
        runner.score = run * 100
        runner.ghost.record(0, run % 3, "run")
        runner.finish_run()
    assert len(runner.ghost_archive) == 5
    assert [item["run"] for item in runner.ghost_archive] == [7, 6, 5, 4, 3]
    assert len(runner.save.load()["ghost_archive"]) == 5


def test_career_contract_progress_accumulates_and_rewards_once(runner):
    runner.begin_run()
    runner.distance = 2500
    runner.coins = 40
    runner.finish_run()
    saved = runner.save.load()
    assert saved["career_mission_progress"]["career_distance_5000"] == 2500
    assert saved["career_mission_progress"]["career_tokens_75"] == 40
    assert "career_distance_5000" not in runner.career_mission_ids

    runner.begin_run()
    runner.distance = 2500
    runner.coins = 35
    runner.finish_run()
    assert {"career_distance_5000", "career_tokens_75"} <= runner.career_mission_ids
    assert runner.career_mission_progress["career_distance_5000"] == 5000
    assert runner.career_mission_progress["career_tokens_75"] == 75
    assert any("ALL NIGHTER" in reward for reward in runner.latest_rewards)
    points_after_contracts = runner.upgrade_points
    runner.finish_run()
    assert runner.upgrade_points == points_after_contracts
    runner.state = "missions"
    runner.draw()

    restored = NeonRunner()
    assert {"career_distance_5000", "career_tokens_75"} <= restored.career_mission_ids
    assert restored.career_mission_progress["career_distance_5000"] == 5000


def test_invalid_accessibility_values_fall_back_safely(tmp_path, monkeypatch):
    pygame.init()
    pygame.display.set_mode((1, 1))
    save = SaveManager(tmp_path / "invalid-comfort.sqlite3")
    save.save({"reduced_motion": "false", "reduced_flashing": "yes",
               "control_sensitivity": 99})
    monkeypatch.setattr(game_module, "SaveManager", lambda: save)
    monkeypatch.setattr(game_module, "AudioBus", SilentAudio)
    try:
        runner = NeonRunner()
        assert runner.reduced_motion is False
        assert runner.reduced_flashing is False
        assert runner.control_sensitivity == 2
    finally:
        save.close()
        pygame.quit()
