import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from engine.analytics import AdaptiveDifficulty, PlayerAnalytics, RunTelemetry
from engine.replay import GhostReplay
from engine.worlds import WORLDS, active_world, unlocked_worlds
from engine.animation import CharacterAnimationController
from engine.progression import select_missions, select_career_missions
from engine.effects import ParticlePool


def test_telemetry_summarizes_interactions_and_bounds_reactions():
    telemetry = RunTelemetry()
    telemetry.collision("electric_car")
    telemetry.powerup("magnet")
    for index in range(80):
        telemetry.reaction(index / 10)
    summary = telemetry.summary()
    assert summary["collision_count"] == 1
    assert summary["collisions"] == {"electric_car": 1}
    assert summary["powerups"] == {"magnet": 1}
    assert len(summary["reaction_samples"]) == 64


def test_analytics_history_is_bounded_and_coaching_uses_recent_runs():
    analytics = PlayerAnalytics()
    summary = {"distance": 100, "coins": 2, "collision_count": 1,
               "dash_clears": 0, "near_misses": 0, "jumps": 5,
               "jump_successes": 1, "slides": 0, "slide_successes": 0,
               "collisions": {"gate": 1}}
    for _ in range(105):
        analytics.record(summary, 2)
    assert len(analytics.runs) == 100
    assert analytics.totals["runs"] == 105
    assert analytics.preferred_lane == 2
    assert "jump success" in analytics.coach()
    assert len(PlayerAnalytics(analytics.to_data()).runs) == 100


def test_analytics_ignores_malformed_saved_run_values():
    analytics = PlayerAnalytics({"runs": [{"jumps": "many", "powerups": "bad",
                                            "collisions": {"fence": "lots"},
                                            "reaction_samples": ["bad", -1, .2]}]})
    summary = analytics.runs[0]
    assert summary["jumps"] == 0
    assert summary["powerups"] == {}
    assert summary["collisions"]["fence"] == 0
    assert summary["reaction_samples"] == [.2]


def test_adaptive_difficulty_is_gradual_and_clamped():
    difficulty = AdaptiveDifficulty("challenge", 1.0)
    first = difficulty.observe(True, .2)
    assert 1.0 < first < 1.16
    for _ in range(500):
        difficulty.observe(True, 0)
    assert difficulty.factor <= 1.16
    difficulty.set_preference("relaxed")
    assert difficulty.preference == "relaxed"


def test_analytics_run_result_modulates_adaptive_difficulty_gradually():
    difficulty = AdaptiveDifficulty("balanced", 1.0)
    lower = difficulty.observe_run({"successful_avoids": 0, "collision_count": 3,
                                    "elapsed": 12, "average_reaction": .9})
    assert .90 < lower < 1.0
    upper = difficulty.observe_run({"successful_avoids": 10, "collision_count": 0,
                                    "elapsed": 90, "average_reaction": .2})
    assert lower < upper < 1.16


def test_adaptive_difficulty_includes_jump_slide_and_dash_outcomes():
    basic = AdaptiveDifficulty("balanced", 1.0)
    action_aware = AdaptiveDifficulty("balanced", 1.0)
    basic_result = basic.observe_run({"successful_avoids": 8, "collision_count": 1,
                                      "elapsed": 50, "average_reaction": .5})
    action_result = action_aware.observe_run({"successful_avoids": 8, "collision_count": 1,
                                              "elapsed": 50, "average_reaction": .5,
                                              "jumps": 8, "jump_successes": 2,
                                              "slides": 4, "slide_successes": 1,
                                              "dash_activations": 3, "dash_clears": 0,
                                              "powerup_count": 2})
    assert .82 <= action_result < basic_result <= 1.16


def test_ghost_replay_sampling_and_untrusted_save_validation():
    replay = GhostReplay([[1, 1, "run", 0, 0, 0], ["bad"], [0, 9, "unknown", 0, 0, 0]])
    assert len(replay.samples) == 2
    assert replay.samples[0][0] == 0
    assert replay.at(0)["lane"] == 2
    replay.record(.05, 2, "dash", dash=True)
    assert len(replay.samples) == 2  # The persisted replay already has a later sample.
    replay.record(2, 1, "run")
    assert replay.to_data()[-1][2] == "run"
    assert replay.at(3) is None
    replay.record(None, "invalid", "run")


def test_worlds_unlock_by_profile_and_rotate_by_distance():
    assert [world.key for world in unlocked_worlds(1)] == ["city"]
    assert len(unlocked_worlds(7)) == len(WORLDS)
    assert active_world(0, 5, "city").key == "city"
    assert active_world(5000, 5, "city").key == "metro"
    assert active_world(0, 1, "unlocked_invalid").key == "city"


def test_animation_reactions_are_prioritized_and_do_not_change_physics_state():
    animation = CharacterAnimationController()
    assert animation.trigger("jump_prep")
    assert animation.update(.02, "jump") == "jump_prep"
    assert animation.trigger("hit")
    assert not animation.trigger("powerup")
    assert animation.update(.10, "fall") == "hit"
    assert animation.update(.30, "fall") == "fall"


def test_particle_bursts_and_trails_are_bounded_and_respect_reduced_motion():
    particles = ParticlePool(seed=7)
    particles.emit_burst(10, 20, (255, 80, 120))
    assert len(particles.particles) == 14
    particles.emit_trail(10, 20, (60, 220, 240))
    assert len(particles.particles) == 16
    particles.emit_burst(10, 20, (255, 80, 120), reduced_motion=True)
    assert len(particles.particles) == 16
    particles.update(.6)
    assert particles.particles == []


def test_particle_loop_capacity_glow_and_expiry_white_box_paths():
    pygame.init()
    pygame.display.set_mode((960, 540))
    try:
        particles = ParticlePool(seed=11)
        particles.emit(100, 200, (63, 231, 235))
        assert len(particles.particles) == 6
        particles.emit_burst(100, 200, (255, 84, 155))
        assert len(particles.particles) == 20

        particles.particles = [
            {"x": 100.0, "y": 200.0, "vx": 10.0, "vy": -20.0,
             "life": 0.40, "color": (63, 231, 235)},
            {"x": 110.0, "y": 210.0, "vx": 5.0, "vy": 5.0,
             "life": 0.01, "color": (255, 84, 155)},
        ]
        surface = pygame.Surface((960, 540), pygame.SRCALPHA)
        particles.draw(surface, glow_enabled=True)
        particles.draw(surface, glow_enabled=False)
        particles.update(.02)
        assert len(particles.particles) == 1
        particles.update(1.0)
        assert particles.particles == []

        particles.emit_trail(200, 300, (255, 207, 95), reduced_motion=False)
        assert len(particles.particles) == 2
        particles.emit(200, 300, (255, 207, 95), reduced_motion=True)
        particles.emit_burst(200, 300, (255, 207, 95), reduced_motion=True)
        particles.emit_trail(200, 300, (255, 207, 95), reduced_motion=True)
        assert len(particles.particles) == 2
        particles.clear()
        assert particles.particles == []

        full = ParticlePool(seed=12)
        full.particles = [{
            "x": 1.0, "y": 1.0, "vx": 0.0, "vy": 0.0,
            "life": 0.3, "color": (255, 255, 255),
        }] * 64
        full.emit(1, 1, (255, 255, 255))
        full.emit_burst(1, 1, (255, 255, 255))
        full.emit_trail(1, 1, (255, 255, 255))
        assert len(full.particles) == 64
    finally:
        pygame.quit()


def test_mission_selection_starts_familiar_then_targets_recent_skill_gaps():
    analytics = PlayerAnalytics()
    assert [goal.key for goal in select_missions(analytics, set())] == [
        "distance_1000", "tokens_20", "dash_5"]
    weak_jump = {"jumps": 8, "jump_successes": 1, "slides": 4,
                 "slide_successes": 4, "powerups": {"shield": 2}}
    for _ in range(3):
        analytics.record(weak_jump, 1)
    selected = select_missions(analytics, set(), ())
    assert "jumps_3" in {goal.key for goal in selected}


def test_career_mission_selection_avoids_claimed_and_recent_goals():
    analytics = PlayerAnalytics()
    initial = select_career_missions(analytics, set(), ())
    assert [goal.key for goal in initial] == ["career_distance_5000", "career_tokens_75"]
    selected = select_career_missions(analytics, {initial[0].key}, (initial[1].key,))
    assert len(selected) == 2
    assert initial[0] not in selected and initial[1] not in selected


def test_career_missions_target_an_observed_low_success_action():
    analytics = PlayerAnalytics()
    for _ in range(3):
        analytics.record({"jumps": 8, "jump_successes": 1, "slides": 0,
                          "powerups": {}, "dash_activations": 1}, 1)
    selected = select_career_missions(analytics, set(), ())
    assert "career_clean_25" in {goal.key for goal in selected}
