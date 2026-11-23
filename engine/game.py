"""Neon Dash: a quick-to-learn three-lane endless runner."""

from __future__ import annotations

import math
import random
import sys
from datetime import date

import pygame

from database.save_manager import SaveManager
from engine.audio import AudioBus
from engine.assets import AnimatedSprite, AssetPack
from engine.patterns import PatternGenerator
from engine.progression import (ACHIEVEMENTS, MISSIONS, CAREER_MISSIONS, newly_completed,
                                daily_challenge_for, DAILY_CHALLENGES, WEEKLY_CHALLENGES,
                                weekly_challenge_for, select_missions, select_career_missions)
from engine.difficulty import DifficultyCurve
from engine.analytics import PlayerAnalytics, RunTelemetry, AdaptiveDifficulty
from engine.replay import GhostReplay
from engine.effects import ParticlePool
from engine.worlds import WORLDS, active_world, unlocked_worlds
from engine.animation import CharacterAnimationController
from engine.parallax import make_city_layers
from engine.gamefeel import ComboTracker
from engine.svg_art import (entity_surface, glow_surface, panel_surface, runner_surface,
                            road_surface, scaled as scale_svg, skyline_surface, sky_surface)


WIDTH, HEIGHT = 960, 540
FPS = 60
COMFORT_OPTION_COUNT = 16
INK = (8, 11, 23)
PANEL = (13, 20, 38)
WHITE = (239, 245, 248)
MUTED = (154, 173, 196)
CYAN = (63, 231, 235)
PINK = (255, 84, 155)
GOLD = (255, 207, 95)
GREEN = (100, 239, 157)
PLAYER_Y = 432
SAVE_SCHEMA_VERSION = 4

UPGRADES = (
    ("magnet", "MAGNET FIELD", "Longer pull time and wider pickup reach", 5),
    ("dash", "DASH CAPACITOR", "Charge faster; dash lasts longer", 5),
    ("shield", "PHASE SHIELD", "Start with a shield at higher levels", 5),
    ("token", "TOKEN VALUE", "Tokens are worth more run score", 5),
    ("battery", "ENERGY CELLS", "Batteries charge more and appear more often", 5),
)
AVATARS = (
    {"id":"runner", "name":"NOVA", "tag":"BALANCED KIT  /  EVEN STATS", "cost":0,
     "jacket":(49,222,224), "trim":(255,117,134), "hair":(29,29,48)},
    {"id":"violet", "name":"BYTE", "tag":"DASH SPECIALIST  /  +10% DASH TIME", "cost":35,
     "jacket":(176,104,255), "trim":(255,213,93), "hair":(39,27,67)},
    {"id":"solar", "name":"SOL", "tag":"TOKEN SPECIALIST  /  +2 DASH CHARGE PER TOKEN", "cost":70,
     "jacket":(255,153,69), "trim":(255,235,139), "hair":(71,35,29)},
    {"id":"mint", "name":"PIXEL", "tag":"MAGNET SPECIALIST  /  +12% MAGNET REACH", "cost":110,
     "jacket":(87,232,164), "trim":(91,177,255), "hair":(25,56,51)},
)


def saved_level(value: object, default: int = 1) -> int:
    """Return a valid four-step setting level even when a save is stale or edited."""
    if not isinstance(value, (int, float, str)):
        return default
    try:
        return max(0, min(3, int(value)))
    except (TypeError, ValueError, OverflowError):
        return default


def saved_integer(value: object, default: int = 0, maximum: int = 2_147_483_647) -> int:
    """Clamp untrusted persisted counters and use defaults for malformed values."""
    if not isinstance(value, (int, float, str)):
        return default
    try:
        return max(0, min(maximum, int(value)))
    except (TypeError, ValueError, OverflowError):
        return default


class NeonRunner:
    """Procedurally drawn arcade runner with saved records and a first-run tutorial."""

    def __init__(self) -> None:
        pygame.init()
        pygame.display.set_caption("NEON DASH - Afterhours Run")
        self.fullscreen = True
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT),
                                              pygame.FULLSCREEN | pygame.SCALED)
        self.shake_surface = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        self.fx_surface = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        self.clock = pygame.time.Clock()
        self.font = pygame.font.Font(None, 25)
        self.small = pygame.font.Font(None, 19)
        self.body = pygame.font.Font(None, 28)
        self.title = pygame.font.Font(None, 76)
        self.huge = pygame.font.Font(None, 48)
        self.save = SaveManager()
        stored = self.save.load() or {}
        if not isinstance(stored, dict):
            stored = {}
        self.preserved_save_data = dict(stored)
        self.analytics = PlayerAnalytics(stored.get("analytics"))
        self.adaptive = AdaptiveDifficulty(stored.get("difficulty_preference", "balanced"),
                                           stored.get("adaptive_factor", 1.0))
        self.ghost = GhostReplay()
        self.previous_ghost = GhostReplay(stored.get("previous_ghost"))
        self.best_ghost = GhostReplay(stored.get("best_ghost"))
        self.ghost_archive: list[dict] = []
        raw_ghost_archive = stored.get("ghost_archive", [])
        if isinstance(raw_ghost_archive, list):
            for item in raw_ghost_archive[-GhostReplay.MAX_ARCHIVE_RUNS:]:
                if not isinstance(item, dict):
                    continue
                replay = GhostReplay(item.get("samples"))
                if not replay.samples:
                    continue
                self.ghost_archive.append({
                    "run": saved_integer(item.get("run", 0)),
                    "score": saved_integer(item.get("score", 0)),
                    "distance": saved_integer(item.get("distance", 0)),
                    "replay": replay,
                })
            self.ghost_archive.sort(key=lambda item: item["run"], reverse=True)
        self.ghost_archive_selection = min(
            saved_integer(stored.get("ghost_archive_selection", 0)),
            max(0, len(self.ghost_archive) - 1))
        saved_ghost_source = stored.get("ghost_source")
        if saved_ghost_source not in ("best", "previous", "archive", "off"):
            saved_ghost_source = "best" if stored.get("ghost_visible", True) is True else "off"
        if saved_ghost_source == "archive" and not self.ghost_archive:
            saved_ghost_source = "best"
        self.ghost_source = saved_ghost_source
        self.ghost_visible = self.ghost_source != "off"
        self.particles = ParticlePool()
        self.world_id = stored.get("world_id", "city")
        self.world_selection = next((i for i, world in enumerate(WORLDS) if world.key == self.world_id), 0)
        self.unlocked_world_ids = unlocked_worlds(saved_integer(stored.get("profile_level", 1), 1))
        if self.world_id not in self.unlocked_world_ids:
            self.world_id = "city"
        self.best_score = saved_integer(stored.get("best_score", 0))
        self.best_coins = saved_integer(stored.get("best_coins", 0))
        self.tutorial_seen = stored.get("tutorial_seen", False) is True
        self.total_runs = saved_integer(stored.get("total_runs", 0))
        self.upgrade_points = saved_integer(stored.get("upgrade_points", 0))
        self.profile_xp = saved_integer(stored.get("profile_xp", 0))
        self.profile_level = max(1, saved_integer(stored.get("profile_level", 1), 1))
        self.lifetime_distance = saved_integer(stored.get("lifetime_distance", 0))
        self.lifetime_coins = saved_integer(stored.get("lifetime_coins", 0))
        self.lifetime_dash_clears = saved_integer(stored.get("lifetime_dash_clears", 0))
        self.last_run_distance = saved_integer(stored.get("last_run_distance", 0))
        self.last_run_coins = saved_integer(stored.get("last_run_coins", 0))
        self.last_run_dash_clears = saved_integer(stored.get("last_run_dash_clears", 0))
        self.mission_ids = self.saved_ids(stored.get("mission_ids", []), MISSIONS)
        raw_mission_history = stored.get("mission_history", [])
        self.mission_history = [key for key in raw_mission_history
                                if isinstance(raw_mission_history, list)
                                and isinstance(key, str) and key in {goal.key for goal in MISSIONS}][-20:] \
            if isinstance(raw_mission_history, list) else []
        self.active_missions = select_missions(self.analytics, self.mission_ids, tuple(self.mission_history))
        self.run_missions = self.active_missions
        self.career_mission_ids = self.saved_ids(stored.get("career_mission_ids", []), CAREER_MISSIONS)
        raw_career_history = stored.get("career_mission_history", [])
        career_keys = {goal.key for goal in CAREER_MISSIONS}
        self.career_mission_history = [key for key in raw_career_history
                                       if isinstance(raw_career_history, list)
                                       and isinstance(key, str) and key in career_keys][-20:] \
            if isinstance(raw_career_history, list) else []
        raw_career_progress = stored.get("career_mission_progress", {})
        self.career_mission_progress = {
            goal.key: saved_integer(raw_career_progress.get(goal.key, 0))
            for goal in CAREER_MISSIONS
        } if isinstance(raw_career_progress, dict) else {goal.key: 0 for goal in CAREER_MISSIONS}
        raw_career_active = stored.get("career_mission_keys", [])
        career_by_key = {goal.key: goal for goal in CAREER_MISSIONS}
        self.active_career_missions = tuple(dict.fromkeys(
            career_by_key[key] for key in raw_career_active
            if isinstance(raw_career_active, list) and isinstance(key, str)
            and key in career_by_key and key not in self.career_mission_ids
        )) if isinstance(raw_career_active, list) else ()
        if not self.active_career_missions:
            self.active_career_missions = select_career_missions(
                self.analytics, self.career_mission_ids, tuple(self.career_mission_history))
        self.last_run_metrics = self.analytics.runs[-1] if self.analytics.runs else {}
        self.achievement_ids = self.saved_ids(stored.get("achievement_ids", []), ACHIEVEMENTS)
        self.daily_date = date.today().isoformat()
        self.daily_claimed = (stored.get("daily_date") == self.daily_date
                              and stored.get("daily_claimed") is True)
        raw_challenge_history = stored.get("challenge_history", [])
        self.challenge_history = ([item for item in raw_challenge_history
                                   if isinstance(item, dict)
                                   and item.get("period") in ("daily", "weekly")
                                   and isinstance(item.get("key"), str)
                                   and isinstance(item.get("date"), str)][-100:]
                                  if isinstance(raw_challenge_history, list) else [])
        self.daily_claimed = self.daily_claimed or any(
            item["period"] == "daily" and item["date"] == self.daily_date
            for item in self.challenge_history)
        self.daily_goal = daily_challenge_for(date.today())
        self.weekly_key = f"{date.today().isocalendar().year}-W{date.today().isocalendar().week:02d}"
        self.weekly_goal = weekly_challenge_for(date.today())
        saved_week = stored.get("weekly_key")
        saved_week_data = stored.get("weekly_progress", {})
        if saved_week != self.weekly_key or not isinstance(saved_week_data, dict):
            saved_week_data = {}
        self.weekly_progress = {key: saved_integer(saved_week_data.get(key, 0))
                                for key in ("distance", "coins", "dash_clears")}
        self.weekly_claimed = ((saved_week == self.weekly_key and stored.get("weekly_claimed") is True)
                               or any(item["period"] == "weekly" and item["date"] == self.weekly_key
                                      for item in self.challenge_history))
        raw_upgrades = stored.get("upgrades", {})
        if not isinstance(raw_upgrades, dict):
            raw_upgrades = {}
        self.upgrades = {
            key: saved_integer(raw_upgrades.get(key, 0), maximum=maximum)
            for key, _, _, maximum in UPGRADES
        }
        valid_avatar_ids = {item["id"] for item in AVATARS}
        raw_unlocked = stored.get("unlocked_avatars", ["runner"])
        if not isinstance(raw_unlocked, (list, tuple, set)):
            raw_unlocked = []
        self.unlocked_avatars = {item for item in raw_unlocked
                                 if isinstance(item, str) and item in valid_avatar_ids}
        self.unlocked_avatars.add("runner")
        self.avatar_id = stored.get("avatar_id", "runner")
        if not isinstance(self.avatar_id, str) or self.avatar_id not in valid_avatar_ids:
            self.avatar_id = "runner"
        self.avatar_selection = next(i for i, item in enumerate(AVATARS) if item["id"] == self.avatar_id)
        self.reduced_motion = stored.get("reduced_motion", True) is True
        self.reduced_flashing = stored.get("reduced_flashing", True) is True
        self.glow_enabled = stored.get("glow_enabled", True) is True
        self.particles_enabled = stored.get("particles_enabled", True) is True
        self.reflections_enabled = stored.get("reflections_enabled", True) is True
        self.atmosphere_enabled = stored.get("atmosphere_enabled", True) is True
        self.combo_enabled = stored.get("combo_enabled", True) is True
        self.screen_shake_enabled = stored.get("screen_shake_enabled", True) is True
        self.control_sensitivity = min(2, saved_level(stored.get("control_sensitivity", 1), 1))
        self.calm_mode = stored.get("calm_mode", True) is True
        self.break_reminders = stored.get("break_reminders", True) is True
        self.touch_controls = stored.get("touch_controls", False) is True
        self.music_level = saved_level(stored.get("music_level", 2), 2)
        self.sfx_level = saved_level(stored.get("sfx_level", 1), 1)
        self.session_playtime = 0.0
        self.next_break_at = 240.0
        self.break_prompt_timer = 0.0
        self.touch_start = None
        self.comfort_selection = 0
        self.hub_selection = 0
        self.upgrade_selection = 0
        self.state = "menu"
        self.menu_selection = 0
        self.tutorial_page = 0
        self.audio = AudioBus()
        self.assets = AssetPack.from_environment()
        self.patterns = PatternGenerator()
        self.runner_sprite = AnimatedSprite(self.assets)
        self.animation = CharacterAnimationController()
        self.animation_revision = self.animation.revision
        self.city_backdrop = self.assets.background("city")
        self.world_backdrops = {world.key: self.assets.background(world.key) for world in WORLDS}
        self.world_backdrops["city"] = self.city_backdrop
        if self.city_backdrop is not None:
            self.city_backdrop = pygame.transform.scale(self.city_backdrop, (WIDTH, HEIGHT))
        self.apply_audio_levels()
        if hasattr(self.audio, "set_environment"):
            self.audio.set_environment(active_world(0, self.profile_level, self.world_id).key)
        self.current_world_key = active_world(0, self.profile_level, self.world_id).key
        self.world_transition_timer = 0.0
        self.dash_trail_timer = 0.0
        self.reset_run()
        self.skyline = self.make_skyline()
        self.parallax_layers = make_city_layers()
        self.stars = [(random.randrange(WIDTH), random.randrange(20, 235), random.choice((1, 1, 2)))
                      for _ in range(100)]

    def make_skyline(self) -> list[tuple[int, int, int, int, int]]:
        """Create the repeatable city skyline layout."""
        rng = random.Random(1999)
        result = []
        x = -10
        while x < WIDTH + 50:
            w = rng.randrange(40, 105)
            h = rng.randrange(75, 240)
            result.append((x, 275 - h, w, h, rng.randrange(3)))
            x += w + rng.randrange(4, 15)
        return result

    def reset_run(self) -> None:
        """Reset transient state for a new run."""
        self.previous_best_score = 0
        self.lane = 1
        self.draw_lane = 1.0
        self.jump_time = 0.0
        self.jump_duration = .78
        self.jump_elapsed = 0.0
        self.slide_time = 0.0
        self.hit_cooldown = 0.0
        self.combo = ComboTracker()
        self.shake_time = 0.0
        self.shake_strength = 0.0
        self.shake_phase = 0.0
        self.magnet_time = 0.0
        self.dash_time = 0.0
        self.dash_trail_timer = 0.0
        self.dash_charge = 0.0
        self.distance = 0.0
        self.score = 0
        self.bonus_score = 0
        self.distance_score = 0.0
        self.token_score_total = 0
        self.coins = 0
        self.speed = 150.0 if self.calm_mode else 190.0
        self.spawn_timer = 0.0
        self.entities: list[dict] = []
        self.elapsed = 0.0
        self.hits = 0
        self.shield = min(3, self.upgrades.get("shield", 0) // 2)
        self.message = ""
        self.message_timer = 0.0
        self.tutorial_hint_timer = 0.0
        self.stripe_scroll = 0.0
        self.score_boost_time = 0.0
        self.overdrive_time = 0.0
        self.coin_bonus_time = 0.0
        self.danger_audio_time = 0.0
        self.run_level = 1
        self.dash_clears = 0
        self.run_finalized = False
        self.latest_rewards: list[str] = []
        self.telemetry = RunTelemetry()
        self.ghost = GhostReplay()
        self.particles.clear()

    def persist(self) -> None:
        """Save the current player profile and run state."""
        self.save.save({**self.preserved_save_data,
                        "schema_version": SAVE_SCHEMA_VERSION,
                        "best_score": self.best_score, "best_coins": self.best_coins,
                        "tutorial_seen": self.tutorial_seen, "total_runs": self.total_runs,
                        "upgrade_points": self.upgrade_points, "profile_xp": self.profile_xp,
                        "profile_level": self.profile_level, "upgrades": self.upgrades,
                        "unlocked_avatars": sorted(self.unlocked_avatars), "avatar_id": self.avatar_id,
                        "reduced_motion": self.reduced_motion, "calm_mode": self.calm_mode,
                        "reduced_flashing": self.reduced_flashing,
                        "glow_enabled": self.glow_enabled,
                        "particles_enabled": self.particles_enabled,
                        "reflections_enabled": self.reflections_enabled,
                        "atmosphere_enabled": self.atmosphere_enabled,
                        "combo_enabled": self.combo_enabled,
                        "screen_shake_enabled": self.screen_shake_enabled,
                        "control_sensitivity": self.control_sensitivity,
                        "break_reminders": self.break_reminders, "touch_controls": self.touch_controls,
                        "music_level": self.music_level, "sfx_level": self.sfx_level,
                        "lifetime_distance": self.lifetime_distance,
                        "lifetime_coins": self.lifetime_coins,
                        "lifetime_dash_clears": self.lifetime_dash_clears,
                        "last_run_distance": self.last_run_distance,
                        "last_run_coins": self.last_run_coins,
                        "last_run_dash_clears": self.last_run_dash_clears,
                        "mission_ids": sorted(self.mission_ids),
                        "mission_history": self.mission_history,
                        "career_mission_ids": sorted(self.career_mission_ids),
                        "career_mission_history": self.career_mission_history,
                        "career_mission_progress": self.career_mission_progress,
                        "career_mission_keys": [goal.key for goal in self.active_career_missions],
                        "achievement_ids": sorted(self.achievement_ids),
                        "daily_date": self.daily_date,
                        "daily_claimed": self.daily_claimed,
                        "weekly_key": self.weekly_key,
                        "weekly_progress": self.weekly_progress,
                        "weekly_claimed": self.weekly_claimed,
                        "challenge_history": self.challenge_history,
                        "analytics": self.analytics.to_data(),
                        "adaptive_factor": self.adaptive.factor,
                        "difficulty_preference": self.adaptive.preference,
                        "previous_ghost": self.previous_ghost.to_data(),
                        "best_ghost": self.best_ghost.to_data(),
                        "ghost_archive": [
                            {"run": item["run"], "score": item["score"],
                             "distance": item["distance"],
                             "samples": item["replay"].to_data()}
                            for item in self.ghost_archive[:GhostReplay.MAX_ARCHIVE_RUNS]
                        ],
                        "ghost_archive_selection": self.ghost_archive_selection,
                        "ghost_visible": self.ghost_visible,
                        "ghost_source": self.ghost_source,
                        "world_id": self.world_id})

    @staticmethod
    def saved_ids(value: object, goals: tuple) -> set[str]:
        """Keep only persisted IDs that belong to the supplied goals."""
        allowed = {goal.key for goal in goals}
        if not isinstance(value, (list, tuple, set)):
            return set()
        return {item for item in value if isinstance(item, str) and item in allowed}

    def apply_audio_levels(self) -> None:
        """Apply the saved music and effects volume levels."""
        levels = (0.0, 0.08, 0.16, 0.25)
        self.audio.set_music_volume(levels[self.music_level])
        self.audio.set_sfx_volume(levels[self.sfx_level])

    def run(self) -> None:
        """Run the game's event, update, and render loop."""
        while True:
            dt = min(self.clock.tick(FPS) / 1000, 0.04)
            self.handle_events()
            self.update(dt)
            self.draw()

    def toggle_fullscreen(self) -> None:
        """Switch between fullscreen and windowed display modes."""
        fullscreen = not self.fullscreen
        flags = pygame.FULLSCREEN | pygame.SCALED if fullscreen else 0
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT), flags)
        self.fullscreen = fullscreen

    def handle_events(self) -> None:
        """Process queued window, keyboard, mouse, and touch events."""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.persist()
                pygame.quit()
                sys.exit()
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                self.mouse_click(event.pos)
            if event.type == pygame.FINGERDOWN:
                self.touch_controls = True
                self.touch_start = (event.x * WIDTH, event.y * HEIGHT)
            elif event.type == pygame.FINGERUP and self.touch_start is not None:
                self.handle_touch(self.touch_start, (event.x * WIDTH, event.y * HEIGHT))
                self.touch_start = None
            elif event.type == pygame.FINGERUP:
                self.touch_start = None
            if event.type != pygame.KEYDOWN:
                continue
            key = event.key
            if key == pygame.K_F11:
                self.toggle_fullscreen()
                continue
            if self.state == "menu":
                if key in (pygame.K_UP, pygame.K_w):
                    self.menu_selection = (self.menu_selection - 1) % 6
                elif key in (pygame.K_DOWN, pygame.K_s):
                    self.menu_selection = (self.menu_selection + 1) % 6
                elif key in (pygame.K_RETURN, pygame.K_SPACE):
                    self.menu_action(self.menu_selection)
                elif key == pygame.K_t:
                    self.state = "tutorial"
                    self.tutorial_page = 0
                elif key == pygame.K_ESCAPE:
                    pygame.quit()
                    sys.exit()
                elif key == pygame.K_m:
                    self.audio.toggle_mute()
            elif self.state == "upgrades":
                if key == pygame.K_ESCAPE:
                    self.state = "menu"
                elif key in (pygame.K_UP, pygame.K_w):
                    self.upgrade_selection = (self.upgrade_selection - 1) % len(UPGRADES)
                elif key in (pygame.K_DOWN, pygame.K_s):
                    self.upgrade_selection = (self.upgrade_selection + 1) % len(UPGRADES)
                elif key in (pygame.K_RETURN, pygame.K_SPACE):
                    self.buy_upgrade(self.upgrade_selection)
            elif self.state == "avatars":
                if key == pygame.K_ESCAPE:
                    self.state = "menu"
                elif key in (pygame.K_LEFT, pygame.K_a):
                    self.avatar_selection = (self.avatar_selection - 1) % len(AVATARS)
                elif key in (pygame.K_RIGHT, pygame.K_d):
                    self.avatar_selection = (self.avatar_selection + 1) % len(AVATARS)
                elif key in (pygame.K_RETURN, pygame.K_SPACE):
                    self.choose_avatar()
            elif self.state == "comfort":
                if key == pygame.K_ESCAPE:
                    self.state = "menu"
                elif key in (pygame.K_UP, pygame.K_w):
                    self.comfort_selection = (self.comfort_selection - 1) % COMFORT_OPTION_COUNT
                elif key in (pygame.K_DOWN, pygame.K_s):
                    self.comfort_selection = (self.comfort_selection + 1) % COMFORT_OPTION_COUNT
                elif (key in (pygame.K_LEFT, pygame.K_a, pygame.K_RIGHT, pygame.K_d)
                      and self.comfort_selection == 7 and self.ghost_source == "archive"):
                    self.select_ghost_archive(-1 if key in (pygame.K_LEFT, pygame.K_a) else 1)
                elif key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_LEFT, pygame.K_RIGHT, pygame.K_a, pygame.K_d):
                    self.change_comfort(self.comfort_selection)
            elif self.state == "hub":
                if key == pygame.K_ESCAPE:
                    self.state = "menu"
                elif key in (pygame.K_UP, pygame.K_w):
                    self.hub_selection = (self.hub_selection - 1) % 6
                elif key in (pygame.K_DOWN, pygame.K_s):
                    self.hub_selection = (self.hub_selection + 1) % 6
                elif key in (pygame.K_RETURN, pygame.K_SPACE):
                    self.open_hub_page(self.hub_selection)
            elif self.state == "worlds":
                if key in (pygame.K_ESCAPE, pygame.K_BACKSPACE):
                    self.state = "hub"
                elif key in (pygame.K_LEFT, pygame.K_a):
                    self.world_selection = (self.world_selection - 1) % len(WORLDS)
                elif key in (pygame.K_RIGHT, pygame.K_d):
                    self.world_selection = (self.world_selection + 1) % len(WORLDS)
                elif key in (pygame.K_RETURN, pygame.K_SPACE):
                    self.choose_world()
            elif self.state == "challenge_history":
                if key in (pygame.K_ESCAPE, pygame.K_BACKSPACE):
                    self.state = "hub"
            elif self.state in ("missions", "achievements", "statistics", "profile"):
                if key in (pygame.K_ESCAPE, pygame.K_BACKSPACE):
                    self.state = "hub"
            elif self.state == "tutorial":
                if key == pygame.K_ESCAPE:
                    self.state = "menu"
                elif key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_RIGHT):
                    if self.tutorial_page < 2:
                        self.tutorial_page += 1
                    else:
                        self.begin_run()
            elif self.state == "playing":
                self.play_key(key)
            elif self.state == "paused":
                if key in (pygame.K_ESCAPE, pygame.K_p):
                    self.state = "playing"
                elif key in (pygame.K_RETURN, pygame.K_r):
                    self.begin_run()
                elif key == pygame.K_u:
                    self.state = "upgrades"
                elif key == pygame.K_c:
                    self.state = "avatars"
                elif key == pygame.K_q:
                    self.state = "menu"
            elif self.state == "gameover":
                if key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_r):
                    self.begin_run()
                elif key == pygame.K_u:
                    self.state = "upgrades"
                elif key in (pygame.K_ESCAPE, pygame.K_q):
                    self.state = "menu"

    def mouse_click(self, pos: tuple[int, int]) -> None:
        """Dispatch a mouse click to the active screen."""
        x, y = pos
        if self.state == "menu":
            if 320 <= x <= 640:
                for index in range(6):
                    if 188 + index*44 <= y <= 226 + index*44:
                        self.menu_action(index)
                        return
        elif self.state == "playing":
            if x >= 758 and y >= 470:
                self.state = "paused"
                return
            if self.touch_controls:
                for center_x, action in ((350, "left"), (430, "jump"), (510, "slide"),
                                         (590, "right"), (670, "dash")):
                    if (x-center_x)**2 + (y-505)**2 <= 34**2:
                        self.touch_action(action)
                        return
        elif self.state == "tutorial":
            if self.tutorial_page < 2:
                self.tutorial_page += 1
            else:
                self.begin_run()
        elif self.state == "paused":
            if 290 <= y <= 344:
                self.state = "playing"
            elif y >= 427:
                self.state = "menu"
        elif self.state == "gameover":
            if 290 <= y <= 344:
                self.begin_run()
            elif y >= 427:
                self.state = "menu"
        elif self.state == "upgrades":
            if y >= 470:
                self.state = "menu"
                return
            for index in range(len(UPGRADES)):
                if 118 + index*70 <= y <= 178 + index*70:
                    self.upgrade_selection = index
                    self.buy_upgrade(index)
                    return
        elif self.state == "avatars":
            if y >= 485:
                self.state = "menu"
                return
            if x < WIDTH // 2 - 100:
                self.avatar_selection = (self.avatar_selection - 1) % len(AVATARS)
            elif x > WIDTH // 2 + 100:
                self.avatar_selection = (self.avatar_selection + 1) % len(AVATARS)
            else:
                self.choose_avatar()
        elif self.state == "comfort":
            if y >= 482:
                self.state = "menu"
            elif 92 <= y < 92 + COMFORT_OPTION_COUNT * 31:
                index = max(0, min(COMFORT_OPTION_COUNT - 1, (y - 92) // 31))
                self.comfort_selection = index
                self.change_comfort(index)
        elif self.state == "hub":
            if y >= 475:
                self.state = "menu"
            else:
                for index in range(6):
                    row_y = 112 + index * 60
                    if row_y <= y <= row_y + 52:
                        self.hub_selection = index
                        self.open_hub_page(index)
                        break
        elif self.state == "worlds":
            if y >= 470:
                self.state = "hub"
            elif 300 <= y <= 450:
                self.choose_world()
            elif x < WIDTH // 2:
                self.world_selection = (self.world_selection - 1) % len(WORLDS)
            else:
                self.world_selection = (self.world_selection + 1) % len(WORLDS)
        elif self.state in ("missions", "achievements", "statistics", "profile", "challenge_history"):
            if y >= 475:
                self.state = "hub"

    def handle_touch(self, start: tuple[float, float], end: tuple[float, float]) -> None:
        """Translate a touch gesture into a gameplay action."""
        if self.state != "playing":
            return
        dx, dy = end[0]-start[0], end[1]-start[1]
        tap_threshold = (22, 34, 48)[self.control_sensitivity]
        if abs(dx) < tap_threshold and abs(dy) < tap_threshold:
            if end[0] >= 758 and end[1] >= 470:
                self.state = "paused"
            else:
                self.touch_action("jump" if start[1] < HEIGHT * .55 else "slide")
        elif abs(dx) > abs(dy):
            self.touch_action("right" if dx > 0 else "left")
        else:
            self.touch_action("slide" if dy > 0 else "jump")

    def touch_action(self, action: str) -> None:
        """Apply a touch-screen gameplay action."""
        if action == "left":
            previous_lane = self.lane
            self.lane = max(0, self.lane - 1)
            self.record_lane_change(previous_lane, self.lane)
        elif action == "right":
            previous_lane = self.lane
            self.lane = min(2, self.lane + 1)
            self.record_lane_change(previous_lane, self.lane)
        elif action == "jump" and self.jump_time <= 0 and self.slide_time <= 0:
            self.jump_duration = .90 if self.calm_mode else .78
            self.jump_time = self.jump_duration
            self.jump_elapsed = 0.0
            self.telemetry.jumps += 1
            self.animation.trigger("jump_prep")
            self.audio.play("jump")
        elif action == "slide" and self.slide_time <= 0 and self.jump_time <= 0:
            self.slide_time = .82 if self.calm_mode else .72
            self.telemetry.slides += 1
            self.animation.state = "slide"
            self.audio.play("slide")
        elif action == "dash":
            self.activate_dash()

    def record_lane_change(self, previous_lane: int, new_lane: int) -> None:
        """Record a lane input and whether it escaped a nearby hazard lane."""
        if new_lane == previous_lane:
            return
        self.telemetry.lane_changes += 1
        hazard_kinds = {"barrier", "gate", "electric_car", "fence"}
        nearby = [entity for entity in self.entities
                  if entity.get("kind") in hazard_kinds
                  and PLAYER_Y - 112 <= entity.get("y", -10_000) <= PLAYER_Y + 18]
        threatened = any(abs(entity.get("lane", -9) - previous_lane) < .45 for entity in nearby)
        if threatened:
            self.telemetry.lane_change_threats += 1
            if not any(abs(entity.get("lane", -9) - new_lane) < .45 for entity in nearby):
                self.telemetry.lane_change_successes += 1

    def activate_dash(self) -> None:
        """Start a dash when the charge meter is full."""
        if self.dash_charge < 100:
            return
        self.dash_charge = 0
        self.telemetry.dash_activations += 1
        self.dash_time = (1.45 + 0.20 * self.upgrades.get("dash", 0)) * (1.10 if self.avatar_id == "violet" else 1.0)
        self.animation.state = "dash"
        self.message = "DASH! Clear the track!"
        self.message_timer = 1.6
        self.audio.play("dash")

    def open_hub_page(self, selection: int) -> None:
        """Open the records page selected in the hub."""
        self.state = ("missions", "achievements", "statistics", "profile",
                      "worlds", "challenge_history")[selection]

    def choose_world(self) -> None:
        """Select the highlighted world if it is unlocked."""
        world = WORLDS[self.world_selection]
        if self.profile_level < world.unlock_level:
            self.message = f"UNLOCK AT PROFILE LEVEL {world.unlock_level}"
            self.message_timer = 1.5
            return
        self.world_id = world.key
        self.persist()
        if hasattr(self.audio, "set_environment"):
            self.audio.set_environment(world.key)
        self.message = f"{world.name} SELECTED"
        self.message_timer = 1.5
        self.state = "hub"

    def change_comfort(self, index: int) -> None:
        """Cycle a comfort setting and persist the updated preference."""
        if index == 0:
            self.reduced_motion = not self.reduced_motion
        elif index == 1:
            self.calm_mode = not self.calm_mode
        elif index == 2:
            self.music_level = (self.music_level + 1) % 4
        elif index == 3:
            self.sfx_level = (self.sfx_level + 1) % 4
        elif index == 4:
            self.break_reminders = not self.break_reminders
        elif index == 5:
            self.touch_controls = not self.touch_controls
        elif index == 6:
            preferences = tuple(AdaptiveDifficulty.PREFERENCES)
            current = preferences.index(self.adaptive.preference)
            self.adaptive.set_preference(preferences[(current + 1) % len(preferences)])
        elif index == 7:
            modes = ("best", "previous", "archive", "off") if self.ghost_archive else ("best", "previous", "off")
            self.ghost_source = modes[(modes.index(self.ghost_source) + 1) % len(modes)]
            self.ghost_visible = self.ghost_source != "off"
        elif index == 8:
            self.reduced_flashing = not self.reduced_flashing
        elif index == 9:
            self.control_sensitivity = (self.control_sensitivity + 1) % 3
        elif index == 10:
            self.combo_enabled = not self.combo_enabled
            if not self.combo_enabled:
                self.combo.break_chain()
        elif index == 11:
            self.screen_shake_enabled = not self.screen_shake_enabled
            if not self.screen_shake_enabled:
                self.shake_time = self.shake_strength = 0.0
        elif index == 12:
            self.glow_enabled = not self.glow_enabled
        elif index == 13:
            self.particles_enabled = not self.particles_enabled
            if not self.particles_enabled:
                self.particles.clear()
        elif index == 14:
            self.reflections_enabled = not self.reflections_enabled
        elif index == 15:
            self.atmosphere_enabled = not self.atmosphere_enabled
        self.apply_audio_levels()
        self.persist()

    def select_ghost_archive(self, direction: int) -> None:
        """Move the selection through the saved ghost archive."""
        if not self.ghost_archive:
            return
        self.ghost_archive_selection = (self.ghost_archive_selection + direction) % len(self.ghost_archive)
        self.persist()

    def selected_ghost_replay(self) -> GhostReplay | None:
        """Return the replay selected by the ghost visibility setting."""
        if self.ghost_source == "best":
            return self.best_ghost
        if self.ghost_source == "previous":
            return self.previous_ghost
        if self.ghost_source == "archive" and self.ghost_archive:
            return self.ghost_archive[self.ghost_archive_selection]["replay"]
        return None

    def menu_action(self, selection: int) -> None:
        """Activate the selected title-menu item."""
        if selection == 0:
            if not self.tutorial_seen:
                self.tutorial_page = 0
                self.state = "tutorial"
            else:
                self.begin_run()
        elif selection == 1:
            self.upgrade_selection = 0
            self.state = "upgrades"
        elif selection == 2:
            self.state = "avatars"
        elif selection == 3:
            self.tutorial_page = 0
            self.state = "tutorial"
        elif selection == 4:
            self.state = "comfort"
        elif selection == 5:
            self.hub_selection = 0
            self.state = "hub"
        else:
            pygame.quit()
            sys.exit()

    def begin_run(self) -> None:
        """Reset transient state and start a new run."""
        self.reset_run()
        self.run_missions = self.active_missions
        self.adaptive.decisions = 0
        self.adaptive.successes = 0
        self.state = "playing"
        self.tutorial_seen = True
        self.total_runs += 1
        self.shield = min(3, self.upgrades.get("shield", 0) // 2)
        self.persist()

    def upgrade_cost(self, key: str) -> int:
        """Calculate the cost of the next level for an upgrade."""
        return 10 + self.upgrades.get(key, 0) * 10

    def buy_upgrade(self, selection: int) -> None:
        """Purchase the selected upgrade when it is affordable."""
        key, label, _, maximum = UPGRADES[selection]
        level = self.upgrades.get(key, 0)
        cost = self.upgrade_cost(key)
        if level >= maximum:
            self.message, self.message_timer = "UPGRADE MAXED", 1.2
        elif self.upgrade_points < cost:
            self.message, self.message_timer = f"NEED {cost-self.upgrade_points} MORE UPGRADE POINTS", 1.2
        else:
            self.upgrade_points -= cost
            self.upgrades[key] = level + 1
            self.message, self.message_timer = f"{label}  LEVEL {level+1}", 1.4
            self.audio.play("level")
            self.persist()

    def choose_avatar(self) -> None:
        """Unlock or select the highlighted runner."""
        avatar = AVATARS[self.avatar_selection]
        avatar_id = avatar["id"]
        if avatar_id not in self.unlocked_avatars:
            if self.upgrade_points < avatar["cost"]:
                self.message = f"NEED {avatar['cost']-self.upgrade_points} MORE UPGRADE POINTS"
                self.message_timer = 1.4
                return
            self.upgrade_points -= avatar["cost"]
            self.unlocked_avatars.add(avatar_id)
        self.avatar_id = avatar_id
        self.persist()
        self.audio.play("level")

    def play_key(self, key: int) -> None:
        """Handle keyboard controls during gameplay."""
        if key in (pygame.K_LEFT, pygame.K_a):
            previous_lane = self.lane
            self.lane = max(0, self.lane - 1)
            self.record_lane_change(previous_lane, self.lane)
        elif key in (pygame.K_RIGHT, pygame.K_d):
            previous_lane = self.lane
            self.lane = min(2, self.lane + 1)
            self.record_lane_change(previous_lane, self.lane)
        elif key in (pygame.K_UP, pygame.K_w, pygame.K_SPACE):
            if self.jump_time <= 0 and self.slide_time <= 0:
                self.jump_duration = .90 if self.calm_mode else .78
                self.jump_time = self.jump_duration
                self.jump_elapsed = 0.0
                self.telemetry.jumps += 1
                self.animation.trigger("jump_prep")
                self.audio.play("jump")
        elif key in (pygame.K_DOWN, pygame.K_s):
            if self.slide_time <= 0 and self.jump_time <= 0:
                self.slide_time = 0.82 if self.calm_mode else 0.72
                self.telemetry.slides += 1
                self.animation.state = "slide"
                self.audio.play("slide")
        elif key == pygame.K_e:
            self.activate_dash()
        elif key == pygame.K_m:
            self.audio.toggle_mute()
        elif key in (pygame.K_ESCAPE, pygame.K_p):
            self.state = "paused"

    def update(self, dt: float) -> None:
        """Advance gameplay systems by one frame."""
        self.particles.update(max(0.0, dt))
        self.combo.update(dt)
        self.shake_time = max(0.0, self.shake_time - max(0.0, dt))
        if self.shake_time == 0:
            self.shake_strength = 0.0
        else:
            self.shake_phase += max(0.0, dt) * 42
        if self.state != "playing":
            self.animation.update(dt, "idle" if self.state == "menu" else self.animation.state)
            self.runner_sprite.set_animation(self.animation_asset_key(self.animation.state))
            if self.animation_revision != self.animation.revision:
                self.runner_sprite.restart()
                self.animation_revision = self.animation.revision
            self.runner_sprite.update(dt)
            self.audio.set_boost(False)
            return
        self.elapsed += dt
        self.session_playtime += dt
        self.break_prompt_timer = max(0, self.break_prompt_timer - dt)
        if self.break_reminders and self.session_playtime >= self.next_break_at:
            self.break_prompt_timer = 8.0
            self.next_break_at += 240.0
        boost_speed = self.dash_time > 0 or self.overdrive_time > 0
        self.distance += self.speed * dt * (1.8 if boost_speed else 1.0)
        world = active_world(self.distance, self.profile_level, self.world_id)
        if world.key != self.current_world_key:
            self.current_world_key = world.key
            self.world_transition_timer = .75
            self.message = world.name
            self.message_timer = 1.4
        if hasattr(self.audio, "set_environment"):
            self.audio.set_environment(world.key)
        self.speed = DifficultyCurve.speed(self.elapsed, self.calm_mode, self.overdrive_time > 0,
                                           self.adaptive.factor)
        self.score_boost_time = max(0, self.score_boost_time - dt)
        self.overdrive_time = max(0, self.overdrive_time - dt)
        self.coin_bonus_time = max(0, self.coin_bonus_time - dt)
        self.distance_score += self.speed * dt * (1.8 if boost_speed else 1.0) / 5 * (2 if self.score_boost_time > 0 else 1)
        self.score = int(self.distance_score) + self.token_score_total + self.bonus_score
        new_level = 1 + self.score // 2500
        if new_level > self.run_level:
            self.run_level = new_level
            self.message = f"LEVEL {self.run_level} - FASTER ROUTE"
            self.message_timer = 1.5
            self.audio.play("level")
        self.draw_lane += (self.lane - self.draw_lane) * min(1, dt * 14)
        was_jumping = self.jump_time > 0
        if was_jumping:
            self.jump_elapsed += dt
        self.jump_time = max(0, self.jump_time - dt)
        if was_jumping and self.jump_time <= 0:
            self.animation.trigger("landing")
        self.slide_time = max(0, self.slide_time - dt)
        self.hit_cooldown = max(0, self.hit_cooldown - dt)
        self.magnet_time = max(0, self.magnet_time - dt)
        self.dash_time = max(0, self.dash_time - dt)
        self.dash_trail_timer = max(0.0, self.dash_trail_timer - dt)
        if self.dash_time > 0 and self.dash_trail_timer <= 0:
            self.particles.emit_trail(self.lane_x(self.draw_lane, PLAYER_Y), PLAYER_Y - 15,
                                      CYAN, self.reduced_motion or not self.particles_enabled)
            self.dash_trail_timer = .045
        locomotion = ("dash" if self.dash_time > 0 else "slide" if self.slide_time > 0
                      else "jump" if self.jump_time > self.jump_duration * .5
                      else "fall" if self.jump_time > 0 else "run")
        self.animation.update(dt, locomotion)
        self.runner_sprite.set_animation(self.animation_asset_key(self.animation.state))
        if self.animation_revision != self.animation.revision:
            self.runner_sprite.restart()
            self.animation_revision = self.animation.revision
        self.runner_sprite.update(dt)
        self.message_timer = max(0, self.message_timer - dt)
        self.world_transition_timer = max(0.0, self.world_transition_timer - dt)
        self.danger_audio_time = max(0.0, self.danger_audio_time - dt)
        if hasattr(self.audio, "set_intensity"):
            cap = DifficultyCurve.CALM_SPEED_CAP if self.calm_mode else DifficultyCurve.STANDARD_SPEED_CAP
            self.audio.set_intensity(min(1.0, .12 + self.speed / cap * .55
                                         + (.34 if self.danger_audio_time > 0 else 0.0)))
        self.audio.set_boost(self.dash_time > 0 or self.magnet_time > 0 or
                             self.score_boost_time > 0 or self.overdrive_time > 0)
        self.stripe_scroll = (self.stripe_scroll + self.speed * dt * (0.35 if self.reduced_motion else 1.0)) % 110

        self.spawn_timer -= dt
        spawn_gap = DifficultyCurve.spawn_interval(self.elapsed, self.calm_mode, self.adaptive.factor)
        if self.spawn_timer <= 0:
            self.spawn_pattern()
            if self.calm_mode:
                self.spawn_timer = max(DifficultyCurve.CALM_SPAWN_FLOOR,
                                       spawn_gap * random.uniform(0.90, 1.10))
            else:
                self.spawn_timer = spawn_gap * random.uniform(0.86, 1.14)

        move_speed = self.speed * (1.9 if self.dash_time > 0 else 1.25 if self.overdrive_time > 0 else 1)
        self.ghost.record(self.elapsed, self.lane,
                          "jump" if self.jump_time > 0 else "slide" if self.slide_time > 0 else "run",
                          self.jump_time, self.slide_time, self.dash_time > 0)
        for obj in self.entities[:]:
            previous_y = obj["y"]
            obj["y"] += move_speed * dt
            if obj["kind"] not in ("coin", "battery", "shield", "magnet", "score_boost", "overdrive", "coin_bonus"):
                if obj["y"] >= 270 and "noticed_at" not in obj:
                    obj["noticed_at"] = self.elapsed
            magnet_reach = (80 + 35 * self.upgrades.get("magnet", 0)) * (1.12 if self.avatar_id == "mint" else 1.0)
            if self.magnet_time > 0 and obj["kind"] == "coin" and obj["y"] > PLAYER_Y - magnet_reach:
                obj["lane"] += (self.draw_lane - obj["lane"]) * min(1, dt * 3)
            if obj["kind"] in ("coin", "battery", "shield", "magnet", "score_boost", "overdrive", "coin_bonus"):
                if abs(obj["y"] - PLAYER_Y) < 24 and abs(obj["lane"] - self.draw_lane) < 0.47:
                    self.particles.emit(self.lane_x(obj["lane"], obj["y"]), obj["y"],
                                        GOLD if obj["kind"] == "coin" else CYAN,
                                        self.reduced_motion or not self.particles_enabled)
                    self.pickup(obj)
                    self.entities.remove(obj)
                    continue
            elif previous_y < PLAYER_Y <= obj["y"]:
                lane_gap = abs(obj["lane"] - self.lane)
                reaction = max(0.0, self.elapsed - obj.get("noticed_at", self.elapsed))
                if 0.45 <= lane_gap < 1.35:
                    self.telemetry.near_misses += 1
                    self.telemetry.reaction(reaction)
                    self.adaptive.observe(True, reaction)
                    self.add_combo_event(15, "NEAR MISS")
                    self.danger_audio_time = .9
                    self.audio.play("near_miss")
                if lane_gap < 0.45 and self.dash_time > 0:
                    self.dash_clears += 1
                    self.telemetry.dash_clears += 1
                    self.telemetry.reaction(reaction)
                    self.adaptive.observe(True, reaction)
                    points = 35 * (2 if self.score_boost_time > 0 else 1)
                    self.bonus_score += points
                    self.message = "CLEAN DASH +35"
                    self.message_timer = 0.6
                    self.add_combo_event(points, "DASH")
                elif lane_gap < 0.45 and obj["kind"] == "barrier" and self.jump_time > 0.14:
                    self.telemetry.jump_successes += 1
                    self.telemetry.reaction(reaction)
                    self.adaptive.observe(True, reaction)
                    points = 40 * (2 if self.score_boost_time > 0 else 1)
                    self.bonus_score += points
                    self.message = "NICE JUMP +40"
                    self.message_timer = 0.65
                    self.add_combo_event(points, "JUMP")
                elif lane_gap < 0.45 and obj["kind"] == "gate" and self.slide_time > 0.12:
                    self.telemetry.slide_successes += 1
                    self.telemetry.reaction(reaction)
                    self.adaptive.observe(True, reaction)
                    points = 40 * (2 if self.score_boost_time > 0 else 1)
                    self.bonus_score += points
                    self.message = "NICE MOVE +40"
                    self.message_timer = 0.65
                    self.add_combo_event(points, "SLIDE")
                elif lane_gap < 0.45:
                    self.take_hit(obj["kind"])
            if obj["y"] > HEIGHT + 80:
                self.entities.remove(obj)

        if self.elapsed < 9:
            self.tutorial_hint_timer = 9 - self.elapsed

    def spawn_pattern(self) -> None:
        """Add a procedurally generated entity pattern with a safe route."""
        world = active_world(self.distance, self.profile_level, self.world_id)
        movement_speed = self.speed * (1.9 if self.dash_time > 0 else
                                       1.25 if self.overdrive_time > 0 else 1.0)
        hazards = [entity for entity in self.entities
                   if entity.get("kind") in PatternGenerator.HAZARD_KINDS]
        for _ in range(8):
            candidate = self.patterns.generate(self.upgrades.get("battery", 0),
                                               self.adaptive.factor, world.hazards)
            candidate_hazards = [entity for entity in candidate
                                 if entity.get("kind") in PatternGenerator.HAZARD_KINDS]
            if (not candidate_hazards or PatternGenerator.has_reachable_route(
                    hazards + candidate_hazards, movement_speed, self.lane)):
                self.entities.extend(candidate)
                return
        # If eight draws are all unsafe, leave a brief empty row instead of
        # placing a hazard or a tempting pickup into a compromised route.

    def add_combo_event(self, base_points: int, event: str) -> int:
        """Award points for an action and update the combo chain."""
        if not self.combo_enabled:
            return 0
        bonus = self.combo.trigger(base_points)
        self.bonus_score += bonus
        if self.combo.count in (2, 4, 7, 10):
            self.message = f"{event} COMBO x{self.combo.count}  +{bonus}"
            self.message_timer = .75
            self.audio.play("combo")
        return bonus

    def start_screen_shake(self, duration: float, strength: float) -> None:
        """Start an impact shake when accessibility settings allow it."""
        if self.screen_shake_enabled and not self.reduced_motion:
            self.shake_time = max(self.shake_time, duration)
            self.shake_strength = max(self.shake_strength, strength)

    def pickup(self, obj: dict) -> None:
        """Apply the score, power-up, and visual effect for a pickup."""
        kind = obj["kind"]
        token_points = 0
        effect_color = (GOLD if kind == "coin" else
                        {"battery": CYAN, "shield": GREEN, "magnet": PINK,
                         "score_boost": GOLD, "overdrive": CYAN,
                         "coin_bonus": (255, 145, 70)}.get(kind, WHITE))
        self.particles.emit_burst(self.lane_x(self.draw_lane, PLAYER_Y), PLAYER_Y - 28,
                                  effect_color, self.reduced_motion or not self.particles_enabled)
        if kind != "coin":
            self.animation.trigger("powerup")
        if kind == "coin":
            token_amount = 2 if self.coin_bonus_time > 0 else 1
            self.coins += token_amount
            self.telemetry.coins += token_amount
            token_points = 25 + 5*self.upgrades.get("token", 0)
            self.token_score_total += token_points * (2 if self.score_boost_time > 0 else 1)
            self.dash_charge = min(100, self.dash_charge + token_amount * (8 + 2*self.upgrades.get("dash", 0) + (2 if self.avatar_id == "solar" else 0)))
            self.message = f"+{token_amount} NEON TOKEN" if token_amount > 1 else "+1 NEON TOKEN"
            self.message_timer = 0.55
            self.audio.play("coin")
        elif kind == "battery":
            self.telemetry.powerup(kind)
            self.dash_charge = min(100, self.dash_charge + 35 + 15*self.upgrades.get("battery", 0))
            self.message, self.message_timer = f"DASH CHARGE +{35+15*self.upgrades.get('battery',0)}", 1.0
            self.audio.play("battery")
        elif kind == "shield":
            self.telemetry.powerup(kind)
            self.shield = min(1 + self.upgrades.get("shield", 0)//2, self.shield + 1)
            self.message, self.message_timer = "PHASE SHIELD READY", 1.1
            self.audio.play("shield")
        elif kind == "magnet":
            self.telemetry.powerup(kind)
            self.magnet_time = 6.0 + self.upgrades.get("magnet", 0) * 2
            self.message, self.message_timer = f"TOKEN MAGNET — {self.magnet_time:.0f} SEC", 1.2
            self.audio.play("magnet")
        elif kind == "score_boost":
            self.telemetry.powerup(kind)
            self.score_boost_time = 8.0
            self.message, self.message_timer = "DOUBLE SCORE — 8 SEC", 1.2
            self.audio.play("boost")
        elif kind == "overdrive":
            self.telemetry.powerup(kind)
            self.overdrive_time = 6.0
            self.message, self.message_timer = "OVERDRIVE — FULL THROTTLE", 1.2
            self.audio.play("boost")
        elif kind == "coin_bonus":
            self.telemetry.powerup(kind)
            self.coin_bonus_time = 6 + .5 * self.upgrades.get("token", 0)
            self.message, self.message_timer = "TOKEN DOUBLER  /  6 SEC", 1.1
            self.audio.play("coin_bonus")
        self.add_combo_event(token_points if kind == "coin" else 20, "PICKUP")

    def take_hit(self, collision_kind: str = "hazard") -> None:
        """Apply collision consequences, including shield absorption."""
        if self.hit_cooldown > 0:
            return
        self.particles.emit_burst(self.lane_x(self.draw_lane, PLAYER_Y), PLAYER_Y - 30,
                                  PINK if not self.shield else CYAN,
                                  self.reduced_motion or not self.particles_enabled)
        self.combo.break_chain()
        self.audio.play("hit")
        self.telemetry.collision(collision_kind)
        self.adaptive.observe(False, .25)
        self.hit_cooldown = 1.25
        if self.shield:
            self.start_screen_shake(.055, 1.5)
            self.animation.trigger("shield")
            self.shield = 0
            self.message = "SHIELD ABSORBED THE HIT"
            self.message_timer = 1.2
            return
        self.animation.trigger("hit")
        self.start_screen_shake(.14, 2.8)
        self.hits += 1
        self.speed = max(170, self.speed - 22)
        self.message = f"BUMP! {max(0, 3-self.hits)} HEARTS LEFT"
        self.message_timer = 1.1
        if self.hits >= 3:
            self.finish_run()

    def finish_run(self) -> None:
        """Finalize the run, record results, and grant earned rewards."""
        if self.run_finalized:
            return
        self.run_finalized = True
        self.state = "gameover"
        self.animation.trigger("defeat")
        self.telemetry.elapsed = self.elapsed
        self.telemetry.distance = int(self.distance)
        self.telemetry.score = int(self.score)
        self.telemetry.coins = self.coins
        self.telemetry.dash_clears = self.dash_clears
        run_summary = self.telemetry.summary()
        run_summary["difficulty_factor"] = self.adaptive.factor
        run_summary["difficulty_preference"] = self.adaptive.preference
        self.analytics.record(run_summary, self.lane)
        summary = self.analytics.runs[-1]
        summary["powerup_count"] = sum(summary.get("powerups", {}).values())
        summary["elapsed"] = int(self.elapsed)
        summary["consistency"] = self.analytics.performance_consistency()
        self.last_run_metrics = summary
        self.adaptive.observe_run(summary)
        self.previous_ghost = self.ghost
        if self.ghost.samples:
            self.ghost_archive.insert(0, {
                "run": self.total_runs, "score": int(self.score),
                "distance": int(self.distance), "replay": self.ghost,
            })
            self.ghost_archive = self.ghost_archive[:GhostReplay.MAX_ARCHIVE_RUNS]
            self.ghost_archive_selection = 0
        self.previous_best_score = self.best_score
        if self.score >= self.best_score:
            self.best_ghost = self.ghost
        self.unlocked_world_ids = unlocked_worlds(self.profile_level)
        self.best_score = max(self.best_score, self.score)
        self.best_coins = max(self.best_coins, self.coins)
        self.lifetime_distance += int(self.distance)
        self.lifetime_coins += self.coins
        self.lifetime_dash_clears += self.dash_clears
        self.last_run_distance = int(self.distance)
        self.last_run_coins = self.coins
        self.last_run_dash_clears = self.dash_clears
        self.latest_rewards = []
        self.upgrade_points += self.coins
        mission_values = {"distance": int(self.distance), "coins": self.coins,
                          "dash_clears": self.dash_clears}
        mission_values.update({
            "lane_changes": self.telemetry.lane_changes,
            "lane_change_successes": self.telemetry.lane_change_successes,
            "jump_successes": self.telemetry.jump_successes,
            "slide_successes": self.telemetry.slide_successes,
            "powerup_count": sum(self.telemetry.powerups.values()),
            "near_misses": self.telemetry.near_misses,
            "successful_avoids": self.telemetry.successful_avoids,
            "elapsed": int(self.elapsed),
        })
        missions = newly_completed(self.run_missions, mission_values, self.mission_ids)
        for mission in missions:
            self.mission_ids.add(mission.key)
            self.upgrade_points += mission.reward
            self.latest_rewards.append(f"{mission.title} +{mission.reward}")
        self.mission_history.extend(goal.key for goal in self.run_missions)
        self.mission_history = self.mission_history[-20:]
        self.active_missions = select_missions(self.analytics, self.mission_ids,
                                               tuple(self.mission_history))
        career_values = {
            "distance": int(self.distance), "coins": self.coins,
            "dash_clears": self.dash_clears,
            "clean_moves": (self.telemetry.jump_successes + self.telemetry.slide_successes
                            + self.telemetry.lane_change_successes),
            "powerup_count": sum(self.telemetry.powerups.values()),
            "successful_avoids": self.telemetry.successful_avoids,
        }
        for goal in self.active_career_missions:
            self.career_mission_progress[goal.key] += career_values.get(goal.metric, 0)
        career_completed = [goal for goal in self.active_career_missions
                            if goal.key not in self.career_mission_ids
                            and self.career_mission_progress[goal.key] >= goal.target]
        for goal in career_completed:
            self.career_mission_ids.add(goal.key)
            self.upgrade_points += goal.reward
            self.latest_rewards.append(f"{goal.title} +{goal.reward}")
        if career_completed:
            self.career_mission_history.extend(goal.key for goal in career_completed)
            self.career_mission_history = self.career_mission_history[-20:]
            unfinished = tuple(goal for goal in self.active_career_missions
                               if goal.key not in self.career_mission_ids)
            additional = select_career_missions(
                self.analytics, self.career_mission_ids, tuple(self.career_mission_history),
                max(0, 2 - len(unfinished)))
            self.active_career_missions = unfinished + additional
        if not self.daily_claimed and mission_values.get(self.daily_goal.metric, 0) >= self.daily_goal.target:
            self.daily_claimed = True
            self.challenge_history.append({"period": "daily", "key": self.daily_goal.key,
                                           "date": self.daily_date})
            self.challenge_history = self.challenge_history[-100:]
            self.upgrade_points += self.daily_goal.reward
            self.latest_rewards.append(f"{self.daily_goal.title} +{self.daily_goal.reward}")
        self.weekly_progress["distance"] += int(self.distance)
        self.weekly_progress["coins"] += self.coins
        self.weekly_progress["dash_clears"] += self.dash_clears
        if (not self.weekly_claimed
                and self.weekly_progress.get(self.weekly_goal.metric, 0) >= self.weekly_goal.target):
            self.weekly_claimed = True
            self.challenge_history.append({"period": "weekly", "key": self.weekly_goal.key,
                                           "date": self.weekly_key})
            self.challenge_history = self.challenge_history[-100:]
            self.upgrade_points += self.weekly_goal.reward
            self.latest_rewards.append(f"{self.weekly_goal.title} +{self.weekly_goal.reward}")
        self.profile_xp += self.score
        old_level = self.profile_level
        self.profile_level = 1 + self.profile_xp // 5000
        self.unlocked_world_ids = unlocked_worlds(self.profile_level)
        stats = {"total_runs": self.total_runs, "lifetime_distance": self.lifetime_distance,
                 "lifetime_coins": self.lifetime_coins,
                 "lifetime_dash_clears": self.lifetime_dash_clears}
        achievements = newly_completed(ACHIEVEMENTS, stats, self.achievement_ids)
        for achievement in achievements:
            self.achievement_ids.add(achievement.key)
            self.upgrade_points += achievement.reward
            self.latest_rewards.append(f"{achievement.title} +{achievement.reward}")
        if self.profile_level > old_level:
            self.animation.trigger("milestone")
            self.message = f"PROFILE LEVEL {self.profile_level}!"
            self.audio.play("level")
        elif self.latest_rewards:
            self.message = self.latest_rewards[-1]
        self.persist()

    def lane_width(self, y: float) -> float:
        """Return the perspective lane width at a screen height."""
        depth = max(0, min(1, (y - 150) / 375))
        return 39 + 82 * depth

    def lane_x(self, lane: float, y: float) -> float:
        """Convert a lane and screen height into its screen x-coordinate."""
        return WIDTH * 0.5 + (lane - 1) * self.lane_width(y)

    def draw(self) -> None:
        """Render the active game screen and display the completed frame."""
        self.draw_city()
        if self.state == "menu":
            self.draw_menu()
        elif self.state == "tutorial":
            self.draw_tutorial()
        elif self.state == "upgrades":
            self.draw_upgrades()
        elif self.state == "avatars":
            self.draw_avatars()
        elif self.state == "comfort":
            self.draw_comfort()
        elif self.state == "hub":
            self.draw_hub()
        elif self.state == "missions":
            self.draw_missions()
        elif self.state == "achievements":
            self.draw_achievements()
        elif self.state == "statistics":
            self.draw_statistics()
        elif self.state == "profile":
            self.draw_profile()
        elif self.state == "worlds":
            self.draw_worlds()
        elif self.state == "challenge_history":
            self.draw_challenge_history()
        else:
            self.draw_run()
            if self.state == "paused":
                self.draw_pause()
            elif self.state == "gameover":
                self.draw_gameover()
        pygame.display.flip()

    def draw_city(self) -> None:
        """Render the current skyline, atmosphere, and city lighting."""
        self.screen.fill((7, 10, 24))
        world = active_world(getattr(self, "distance", 0), self.profile_level, self.world_id)
        theme = world.accent
        backdrop = self.city_backdrop if world.key == "city" else self.world_backdrops.get(world.key)
        custom_backdrop = backdrop is not None
        if not custom_backdrop:
            self.screen.blit(sky_surface(world.sky, theme), (0, 0))
        else:
            self.screen.blit(self.assets.scaled(backdrop, (WIDTH, HEIGHT)), (0, 0))
        for x, y, size in self.stars:
            pygame.draw.rect(self.screen, (66, 102, 139), (x, y, size, size))
        self.draw_environment(world)
        if not custom_backdrop:
            # Slow, depth-layered light trails add restrained parallax to the skyline.
            for layer in range(3):
                spacing = 310 + layer * 110
                offset = int(getattr(self, "distance", 0) * (.015 + layer * .009)) % spacing
                y = 92 + layer * 48
                tint = tuple(max(0, channel // 3) for channel in world.accent)
                for x in range(-spacing, WIDTH + spacing, spacing):
                    px = x - offset + layer * 37
                    pygame.draw.line(self.screen, tint, (px, y), (px + 52, y), 1)
        # Glow behind the elevated track.
        glow = pygame.Surface((WIDTH, 360), pygame.SRCALPHA)
        boost_active = getattr(self, "dash_time", 0) > 0 or getattr(self, "magnet_time", 0) > 0 or getattr(self, "overdrive_time", 0) > 0
        pygame.draw.ellipse(glow, (18, 130 if boost_active else 93, 161, 66 if boost_active else 38), (90, 95, 780, 210))
        pygame.draw.ellipse(glow, (145 if boost_active else 107, 30, 112, 48 if boost_active else 28), (230, 140, 500, 190))
        self.screen.blit(glow, (0, 100))
        if not custom_backdrop:
            for layer in self.parallax_layers:
                layer.draw(self.screen, getattr(self, "distance", 0), world.skyline,
                           theme, self.reduced_motion)
            building_specs = tuple((x, w, h, style) for x, _y, w, h, style in self.skyline)
            self.screen.blit(skyline_surface(building_specs, WIDTH, 275,
                                             (world.skyline, theme), height=285), (0, 0))
            for x, y, w, h, style in self.skyline:
                if style == 1:
                    pygame.draw.line(self.screen, PINK, (x + w // 2, y),
                                     (x + w // 2, y - 15), 2)
                if world.atmosphere == "market" and style == 2:
                    awning_y = min(258, y + h - 34)
                    pygame.draw.rect(self.screen, (71, 43, 83), (x+5, awning_y, w-10, 17))
                    for stripe_x in range(x+8, x+w-8, 11):
                        pygame.draw.line(self.screen, theme, (stripe_x, awning_y),
                                         (stripe_x, awning_y+16), 3)
                    pygame.draw.rect(self.screen, (255, 210, 123),
                                     (x+w//2-11, awning_y+22, 22, 10), 1)
                elif world.atmosphere == "industrial" and style == 2:
                    stack_w = max(7, w//7)
                    pygame.draw.rect(self.screen, (53, 43, 58),
                                     (x+w//2-stack_w//2, y-38, stack_w, 39))
                    pygame.draw.line(self.screen, theme,
                                     (x+w//2-stack_w//2, y-38), (x+w//2+stack_w//2, y-38), 3)
                elif world.atmosphere == "wind" and style == 0:
                    antenna_x = x + w//2
                    pygame.draw.line(self.screen, (116, 137, 162),
                                     (antenna_x, y), (antenna_x, y-28), 2)
                    pygame.draw.line(self.screen, theme,
                                     (antenna_x-9, y-23), (antenna_x+9, y-23), 2)
                elif world.atmosphere == "highway" and style == 1:
                    for lane_y in (y+56, y+68, y+80):
                        pygame.draw.line(self.screen, theme, (x+7, lane_y),
                                         (x+w-7, lane_y), 2)
            if world.atmosphere == "subway":
                for x in range(-80, WIDTH+160, 240):
                    pygame.draw.arc(self.screen, (74, 105, 126),
                                    (x, 176, 300, 190), math.pi, math.tau, 4)
                    pygame.draw.line(self.screen, (96, 143, 158),
                                     (x+22, 271), (x+278, 271), 2)
            elif world.atmosphere == "arcade":
                for y in range(178, 276, 24):
                    for x in range(30 + (y//24 % 2)*12, WIDTH, 48):
                        pygame.draw.rect(self.screen, theme, (x, y, 7, 3))
                pygame.draw.line(self.screen, (86, 60, 155), (0, 269), (WIDTH, 269), 3)
            elif world.atmosphere == "highway":
                for y in (223, 238, 253):
                    pygame.draw.line(self.screen, (31, 86, 123), (0, y), (WIDTH, y), 1)
        pygame.draw.line(self.screen, (37, 58, 82), (0, 275), (WIDTH, 275), 2)
        # Distant rail bridge and luminous signage.
        pygame.draw.rect(self.screen, (19, 26, 43), (0, 278, WIDTH, 34))
        pygame.draw.line(self.screen, (76, 96, 117), (0, 284), (WIDTH, 284), 3)
        for x in range(-20, WIDTH, 100):
            pygame.draw.rect(self.screen, (46, 58, 78), (x, 283, 5, 32))
        self.text(f"{world.name}  /  NIGHT RUN", WIDTH // 2, 289,
                  (154, 183, 204), self.small, center=True)
        if self.world_transition_timer > 0 and not self.reduced_motion:
            fade = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            fade.fill((4, 8, 20, int(74 * self.world_transition_timer / .75)))
            self.screen.blit(fade, (0, 0))

    def draw_environment(self, world) -> None:
        """Layer restrained weather, haze, and light shafts over each world."""
        self.fx_surface.fill((0, 0, 0, 0))
        if not self.atmosphere_enabled:
            self.screen.blit(self.fx_surface, (0, 0))
            return
        atmosphere = world.atmosphere
        if atmosphere in ("neon", "industrial", "highway") and not (
                self.reduced_motion or self.reduced_flashing):
            rain_scroll = int(self.elapsed * (210 if atmosphere == "highway" else 155))
            for index in range(32):
                rx = (index * 137 + rain_scroll) % WIDTH
                ry = (index * 83 + rain_scroll * 2) % 275
                pygame.draw.line(self.fx_surface, (42, 82, 112, 90),
                                 (rx, ry), (rx - 3, ry + 10), 1)
        if atmosphere in ("subway", "industrial", "wind", "highway"):
            drift = 0 if self.reduced_motion else int(self.elapsed * 13)
            haze_color = (151, 185, 199, 19 if self.reduced_motion else 25)
            for index, y in enumerate((220, 256, 294)):
                offset = (drift * (index + 1)) % (WIDTH + 280)
                pygame.draw.ellipse(self.fx_surface, haze_color,
                                   (offset - 280, y, 560, 56))
                pygame.draw.ellipse(self.fx_surface, haze_color,
                                   (offset + WIDTH - 280, y, 560, 56))
        if atmosphere in ("neon", "market", "highway", "industrial"):
            pulse = 0 if self.reduced_flashing else int(8 * math.sin(self.elapsed * 1.4))
            shaft_color = (*world.accent, 13)
            for index in range(4):
                x = 95 + index * 250 + pulse
                pygame.draw.polygon(self.fx_surface, shaft_color,
                                    ((x, 0), (x + 25, 0),
                                     (x + 92, 276), (x - 55, 276)))
        self.screen.blit(self.fx_surface, (0, 0))

    def draw_run(self) -> None:
        """Render gameplay content with the optional camera offset."""
        shake_active = (self.screen_shake_enabled and not self.reduced_motion
                        and self.shake_time > 0 and self.state in ("playing", "gameover"))
        camera_active = self.state == "playing" and not self.reduced_motion
        if not shake_active and not camera_active:
            self.draw_run_content()
            return
        target = self.screen
        self.shake_surface.fill((0, 0, 0, 0))
        self.screen = self.shake_surface
        try:
            self.draw_run_content()
        finally:
            self.screen = target
        fade = min(1.0, self.shake_time / .14) if shake_active else 0.0
        sway = math.sin(self.elapsed * 1.7) * .8 if camera_active else 0.0
        dash_push = -1.5 if camera_active and self.dash_time > 0 else 0.0
        offset_x = sway + math.sin(self.shake_phase) * self.shake_strength * fade
        offset_y = dash_push + math.cos(self.shake_phase * 1.31) * self.shake_strength * fade * .45
        target.blit(self.shake_surface, (round(offset_x), round(offset_y)))

    def draw_run_content(self) -> None:
        """Render the track, entities, runner, and gameplay overlays."""
        # Receding rail corridor and track-bed.
        world = active_world(self.distance, self.profile_level, self.world_id)
        theme = world.accent
        far_y, near_y = 150, 540
        far_half, near_half = 58, 430
        phase = int(self.stripe_scroll / 16) % 16
        self.screen.blit(road_surface(world.track, theme, phase,
                                      reflections=self.reflections_enabled), (0, 0))
        self.fx_surface.fill((0, 0, 0, 0))
        haze = (*world.skyline, 28)
        pygame.draw.polygon(self.fx_surface, haze,
                            ((480 - far_half, far_y), (480 + far_half, far_y),
                             (480 + 190, 258), (480 - 190, 258)))
        for side in (-1, 1):
            pygame.draw.line(self.fx_surface, (*theme, 26),
                             (480 + side * far_half, far_y),
                             (480 + side * near_half, near_y), 16)
            pygame.draw.line(self.fx_surface, (*theme, 132),
                             (480 + side * far_half, far_y),
                             (480 + side * near_half, near_y), 3)
        self.screen.blit(self.fx_surface, (0, 0))
        # Sleepers move toward the runner, making the world feel alive.
        for i in range(9):
            t = ((i / 9) + (self.stripe_scroll / 110)) % 1
            y = far_y + t * (near_y - far_y)
            half = 60 + t * 370
            color = (44 + int(t*22), 53 + int(t*20), 66 + int(t*15))
            pygame.draw.line(self.screen, color, (480-half, int(y)), (480+half, int(y)), max(2, int(2+t*5)))
        for boundary in (-1.5, -0.5, 0.5, 1.5):
            x1 = 480 + boundary * 40
            x2 = 480 + boundary * 121
            pygame.draw.line(self.screen, (65, 89, 111), (int(x1), far_y), (int(x2), near_y), 3 if abs(boundary) == 1.5 else 1)
        # Reflected rail light and soft bloom reinforce the wet track.
        self.fx_surface.fill((0, 0, 0, 0))
        if self.reflections_enabled:
            for side in (-1, 1):
                for i in range(9):
                    t = ((i / 9) + self.stripe_scroll / 160) % 1
                    y = far_y + t * (near_y - far_y)
                    half = far_half + t * (near_half - far_half)
                    x = 480 + side * (half - 6)
                    c = theme if i % 2 else PINK
                    center = (int(x), int(y))
                    pygame.draw.line(self.fx_surface, (*c, max(8, int(26 * (1 - t)))),
                                     center, (center[0], min(HEIGHT, center[1] + int(12 + t * 20))),
                                     max(1, int(2 + t * 2)))
                    pygame.draw.circle(self.fx_surface, (*c, 48), center, max(5, int(8 + t * 8)))
            self.screen.blit(self.fx_surface, (0, 0))
            for side in (-1, 1):
                for i in range(9):
                    t = ((i / 9) + self.stripe_scroll / 160) % 1
                    y = far_y + t * (near_y - far_y)
                    half = far_half + t * (near_half - far_half)
                    x = 480 + side * (half - 6)
                    c = theme if i % 2 else PINK
                    pygame.draw.circle(self.screen, c, (int(x), int(y)), max(2, int(2+t*3)))

        if self.dash_time > 0 and not self.reduced_motion:
            self.fx_surface.fill((0, 0, 0, 0))
            for index in range(18):
                y = 172 + ((index * 37 + int(self.elapsed * 420)) % 340)
                x = (index * 83 + int(self.elapsed * 95)) % WIDTH
                length = 18 + index % 4 * 8
                pygame.draw.line(self.fx_surface, (*theme, 55),
                                 (x, y), (x - 3, min(HEIGHT, y + length)), 2)
            self.screen.blit(self.fx_surface, (0, 0))

        self.fx_surface.fill((0, 0, 0, 0))
        for obj in sorted(self.entities, key=lambda item: item["y"]):
            self.draw_entity(obj)
        self.screen.blit(self.fx_surface, (0, 0))
        playback = self.selected_ghost_replay()
        if self.ghost_visible and playback is not None and playback.samples:
            sample = playback.at(self.elapsed)
            if sample is not None:
                self.draw_ghost(sample)
        self.draw_runner()
        self.particles.draw(self.screen, glow_enabled=self.glow_enabled)
        if self.world_transition_timer > 0 and not self.reduced_motion:
            self.fx_surface.fill((4, 8, 20, int(70 * self.world_transition_timer / .75)))
            pygame.draw.rect(self.fx_surface, (*world.accent, 35),
                             (0, 264, WIDTH, 22))
            self.screen.blit(self.fx_surface, (0, 0))
        self.draw_hud()
        if self.touch_controls:
            self.draw_touch_controls()
        if self.break_prompt_timer > 0:
            self.pill("Take a soft blink break  /  look into the distance", (WIDTH//2, 188), GREEN)
        if self.tutorial_hint_timer > 0:
            hints = ("A / D  CHANGE LANES", "W / SPACE  JUMP BARRIERS", "S  SLIDE UNDER GATES")
            index = min(2, int((9 - self.tutorial_hint_timer) / 3))
            self.pill(hints[index], (WIDTH//2, 110), CYAN)
        if self.message_timer > 0 and self.message:
            self.pill(self.message, (WIDTH//2, 153), GOLD)

    def draw_entity(self, obj: dict) -> None:
        """Render one entity at its perspective-adjusted position."""
        y = obj["y"]
        depth = max(0.04, min(1.2, (y - 140) / 320))
        cx = self.lane_x(obj["lane"], y)
        lane_w = self.lane_width(y)
        scale = max(0.18, depth)
        kind = obj["kind"]
        pickup_colors = {"coin": GOLD, "battery": CYAN, "shield": GREEN,
                         "magnet": PINK, "score_boost": GOLD,
                         "overdrive": CYAN, "coin_bonus": (255, 145, 70)}
        if kind in pickup_colors:
            color = pickup_colors[kind]
            radius = max(4, int((11 if kind == "coin" else 19) * scale))
            center = (int(cx), int(y - radius))
            glow_size = max(16, min(64, round((radius * 3) / 8) * 8))
            if self.glow_enabled:
                glow = glow_surface(color, glow_size)
                self.fx_surface.blit(glow, glow.get_rect(center=center))
            pygame.draw.ellipse(self.screen, (4, 7, 15),
                                (int(cx - radius * 1.3), int(y - 2),
                                 max(3, int(radius * 2.6)), max(2, int(4 * scale))))
        art = self.assets.sprite(kind)
        from_pack = art is not None
        if art is None:
            art = entity_surface(kind)
        if art is not None:
            size = max(8, int(lane_w * (0.38 if kind == "coin" else 0.82) * scale))
            if kind in ("barrier", "gate", "fence", "electric_car", "train"):
                target_size = (max(14, int(lane_w * .82 * scale)),
                               max(18, int(lane_w * 1.05 * scale)))
            else:
                target_size = (size, size)
            if from_pack:
                art = self.assets.scaled(art, target_size)
            else:
                target_size = tuple(max(8, round(value / 4) * 4) for value in target_size)
                art = scale_svg(art, target_size)
            self.screen.blit(art, art.get_rect(midbottom=(int(cx), int(y))))
            return
        if kind == "coin":
            radius = max(4, int(9 * scale))
            pygame.draw.ellipse(self.screen, (116, 68, 19), (int(cx-radius), int(y-radius), radius*2, radius*2))
            pygame.draw.ellipse(self.screen, GOLD, (int(cx-radius+2), int(y-radius+2), radius*2-4, radius*2-4))
            pygame.draw.line(self.screen, (255, 246, 174), (int(cx), int(y-radius+3)), (int(cx), int(y+radius-3)), max(1, radius//3))
        elif kind == "battery":
            w, h = int(25*scale), int(36*scale)
            rect = pygame.Rect(int(cx-w/2), int(y-h), max(8,w), max(11,h))
            pygame.draw.rect(self.screen, (29, 122, 146), rect, border_radius=4)
            pygame.draw.rect(self.screen, CYAN, rect, max(1,int(2*scale)), border_radius=4)
            self.text("E", cx, y-h/2, WHITE, self.body, center=True)
        elif kind in ("shield", "magnet", "score_boost", "overdrive", "coin_bonus"):
            radius = max(8, int(17*scale))
            color = {"shield":GREEN,"magnet":PINK,"score_boost":GOLD,"overdrive":CYAN,"coin_bonus":(255,145,70)}[kind]
            pygame.draw.circle(self.screen, (25,39,58), (int(cx), int(y-radius)), radius)
            pygame.draw.circle(self.screen, color, (int(cx), int(y-radius)), radius, max(1,int(3*scale)))
            icon = {"shield":"S","magnet":"M","score_boost":"2X","overdrive":"O","coin_bonus":"2C"}[kind]
            self.text(icon, cx, y-radius, color, self.small, center=True)
        elif kind == "barrier":
            w, h = lane_w*.72, 50*scale
            base = y
            rect = pygame.Rect(int(cx-w/2), int(base-h), max(10,int(w)), max(9,int(h)))
            pygame.draw.ellipse(self.screen, (6,9,18), (rect.x-5, int(base-4), rect.width+10, max(3,int(10*scale))))
            pygame.draw.rect(self.screen, (28,48,66), rect, border_radius=max(2,int(4*scale)))
            pygame.draw.rect(self.screen, (255,91,123), (rect.x, rect.y, rect.width, max(3,int(8*scale))))
            for side in (-1,1):
                px=int(cx+side*w*.38)
                pygame.draw.rect(self.screen,(66,88,108),(px-int(5*scale),rect.y+int(7*scale),max(3,int(10*scale)),rect.height-int(7*scale)),border_radius=3)
                pygame.draw.circle(self.screen,GOLD,(px,rect.y+int(6*scale)),max(2,int(5*scale)))
            for sx in range(rect.left+8, rect.right-4, max(8,int(14*scale))):
                spark_y=int(rect.y+10+(0 if self.reduced_flashing else 8*math.sin(self.elapsed*17+sx)))
                pygame.draw.circle(self.screen,CYAN,(sx,spark_y),max(1,int(2*scale)))
        elif kind == "gate":
            w, h = lane_w*.85, 72*scale
            top = y-h
            thickness = max(5,int(11*scale))
            pygame.draw.rect(self.screen, (35,73,104), (int(cx-w/2),int(top),max(10,int(w)),thickness),border_radius=3)
            pygame.draw.rect(self.screen, CYAN,(int(cx-w/2),int(top),max(10,int(w)),max(2,int(3*scale))),border_radius=2)
            for side in (-1,1):
                pygame.draw.rect(self.screen,(49,112,142),(int(cx+side*w*.42-thickness/2),int(top),thickness,max(8,int(h))))
            beam_y=int(top+thickness+10*scale)
            points=[]
            for n in range(9):
                points.append((int(cx-w*.4+n*w*.1),beam_y+int((5 if n%2 else -5)*scale*math.sin(self.elapsed*12+ n))))
            if len(points)>1:
                pygame.draw.lines(self.screen,PINK,False,points,max(1,int(2*scale)))
        elif kind == "fence":
            w,h=lane_w*.90,58*scale
            left = int(cx - w / 2)
            top = int(y - h)
            thick = max(2, int(4 * scale))
            for side in (-1,1):
                px=int(cx+side*w*.42)
                pygame.draw.rect(self.screen,(41,76,99),(px-thick,top,thick,int(h)))
                pygame.draw.circle(self.screen,CYAN,(px,top+4),max(2,int(4*scale)))
            for beam in (.30,.60,.88):
                yy=int(top+h*beam)
                color=CYAN if self.reduced_flashing or int(self.elapsed*12+beam*9)%2 else PINK
                pygame.draw.line(self.screen,color,(left,yy),(left+int(w),yy),max(1,int(2*scale)))
            for spark in range(3):
                sx=left+int(w*((spark*.31+(0 if self.reduced_motion else self.elapsed*.23))%1))
                sy=top+int(h*(.25+.5*((spark+(0 if self.reduced_motion else self.elapsed))%1)))
                pygame.draw.circle(self.screen,WHITE,(sx,sy),max(1,int(3*scale)))
        elif kind in ("electric_car", "train"):
            w, h = lane_w*.90, 90*scale
            rect = pygame.Rect(int(cx-w/2),int(y-h),max(15,int(w)),max(16,int(h)))
            pygame.draw.ellipse(self.screen,(7,10,18),(rect.x-8,int(y-5),rect.width+16,max(4,int(12*scale))))
            pygame.draw.rect(self.screen,(24,42,68),rect,border_radius=max(4,int(14*scale)))
            pygame.draw.rect(self.screen,(55,85,121),(rect.x+int(w*.10),rect.y+int(h*.18),int(w*.80),int(h*.42)),border_radius=max(2,int(8*scale)))
            pygame.draw.rect(self.screen,(20,33,54),(rect.x+int(w*.20),rect.y+int(h*.23),int(w*.60),int(h*.22)),border_radius=max(2,int(5*scale)))
            pygame.draw.line(self.screen,CYAN,(rect.x+int(w*.18),rect.bottom-int(h*.14)),(rect.right-int(w*.18),rect.bottom-int(h*.14)),max(2,int(4*scale)))
            pygame.draw.circle(self.screen,GOLD,(rect.x+int(w*.22),rect.bottom-int(h*.20)),max(2,int(4*scale)))
            pygame.draw.circle(self.screen,GOLD,(rect.right-int(w*.22),rect.bottom-int(h*.20)),max(2,int(4*scale)))

    def draw_runner(self) -> None:
        """Render the selected runner and its current animation."""
        center_x = self.lane_x(self.draw_lane, PLAYER_Y)
        avatar = next(item for item in AVATARS if item["id"] == self.avatar_id)
        jacket, trim, hair = avatar["jacket"], avatar["trim"], avatar["hair"]
        jump_phase = max(0.0, min(1.0, 1 - self.jump_time / max(.01, self.jump_duration)))
        jump_lift = int(74 * math.sin(math.pi * jump_phase)) if self.jump_time > 0 else 0
        y = PLAYER_Y - jump_lift
        state = self.animation.state
        pygame.draw.ellipse(self.screen, (3, 6, 14), (int(center_x - 27), PLAYER_Y - 8, 54, 12))
        self.fx_surface.fill((0, 0, 0, 0))
        if self.glow_enabled:
            pygame.draw.circle(self.fx_surface, (*jacket, 28), (int(center_x), int(y - 38)), 31)
        self.screen.blit(self.fx_surface, (0, 0))
        self.runner_sprite.set_animation(self.animation_asset_key(state))
        art = self.runner_sprite.image
        from_pack = art is not None
        if art is None:
            pose = ("slide" if state == "slide" or self.slide_time > 0 else
                    "jump" if state in ("jump", "fall", "jump_prep") or self.jump_time > 0 else
                    state if state in ("dash", "shield") else "run")
            frame = (0 if self.reduced_motion or pose in ("jump", "slide") else
                     int(self.elapsed * 12 * 8 / math.tau) % 8)
            art = runner_surface(jacket, trim, hair, pose, frame)
        if art is not None:
            target_size = (54, 76) if from_pack else (
                (84, 74) if pose == "slide" else (66, 78))
            art = (self.assets.scaled(art, target_size) if from_pack
                   else scale_svg(art, target_size))
            if self.dash_time > 0 and not self.reduced_motion:
                for offset, alpha in ((12, 38), (22, 20)):
                    echo = art.copy()
                    echo.set_alpha(alpha)
                    self.screen.blit(echo, (int(center_x - art.get_width() / 2 - offset),
                                            int(y - art.get_height())))
            self.screen.blit(art, (int(center_x - art.get_width() / 2), int(y - art.get_height())))
            return
        if state == "shield":
            pygame.draw.circle(self.screen, (84, 231, 190), (int(center_x), PLAYER_Y-37), 38, 2)
        if state == "dash":
            pygame.draw.line(self.screen, CYAN, (int(center_x-35), PLAYER_Y-20),
                             (int(center_x+35), PLAYER_Y-20), 3)
        if state == "slide" or self.slide_time > 0:
            # Low, readable sliding silhouette.
            pygame.draw.ellipse(self.screen, (4,7,15,145), (int(center_x-33), PLAYER_Y-1, 66, 16))
            pygame.draw.rect(self.screen,(26,39,64),(int(center_x-30),PLAYER_Y-23,54,19),border_radius=8)
            pygame.draw.rect(self.screen,(20,24,43),(int(center_x-35),PLAYER_Y-12,40,9),border_radius=4)
            pygame.draw.circle(self.screen,(232,176,142),(int(center_x+23),PLAYER_Y-19),10)
            pygame.draw.rect(self.screen,jacket,(int(center_x-4),PLAYER_Y-23,20,4))
            return
        blink = not (self.reduced_motion or self.reduced_flashing) and self.hit_cooldown > 0 and int(self.elapsed*8) % 2 == 0
        if blink:
            return
        # Procedural shaded runner sprite, animated feet, backpack and cyan jacket.
        surf = pygame.Surface((54,76), pygame.SRCALPHA)
        stride = math.sin(self.elapsed * 12) if self.speed > 0 else 0.0
        if state == "dash":
            stride *= .25
        elif state in ("jump", "fall", "jump_prep"):
            stride *= .35
        elif state in ("hit", "shield", "defeat"):
            stride = 0.0
        pygame.draw.ellipse(surf,(2,5,13,150),(7,66,41,8))
        left_knee = (20 + int(stride * 4), 63 - int(stride * 2))
        right_knee = (34 - int(stride * 4), 63 + int(stride * 2))
        left_foot = (16 + int(stride * 7), 72)
        right_foot = (38 - int(stride * 7), 72)
        pygame.draw.lines(surf,(24,27,42),False,((20,53),left_knee,left_foot),8)
        pygame.draw.lines(surf,(24,27,42),False,((34,53),right_knee,right_foot),8)
        pygame.draw.lines(surf,jacket,False,((20,53),left_knee,left_foot),4)
        pygame.draw.lines(surf,jacket,False,((34,53),right_knee,right_foot),4)
        pygame.draw.circle(surf,(73,88,121),left_knee,3)
        pygame.draw.circle(surf,(73,88,121),right_knee,3)
        pygame.draw.line(surf,(24,27,42),left_foot,(left_foot[0]+7,left_foot[1]),5)
        pygame.draw.line(surf,(24,27,42),right_foot,(right_foot[0]+7,right_foot[1]),5)
        pygame.draw.rect(surf,(41,47,75),(10,29,35,33),border_radius=9)
        pygame.draw.rect(surf,(17,26,51),(4,34,10,25),border_radius=4)
        pygame.draw.rect(surf,jacket,(13,31,27,23),border_radius=5)
        arm_swing = int(stride * 7)
        pygame.draw.lines(surf,(38,45,68),False,((15,35),(9-arm_swing,44),(12-arm_swing,53)),7)
        pygame.draw.lines(surf,(38,45,68),False,((38,35),(45+arm_swing,43),(42+arm_swing,52)),7)
        pygame.draw.lines(surf,(230,177,148),False,((15,35),(9-arm_swing,44),(12-arm_swing,53)),4)
        pygame.draw.lines(surf,(230,177,148),False,((38,35),(45+arm_swing,43),(42+arm_swing,52)),4)
        pygame.draw.rect(surf,(244,185,145),(19,10,20,22),border_radius=7)
        pygame.draw.rect(surf,hair,(17,7,25,12),border_radius=6)
        pygame.draw.rect(surf,hair,(15,13,7,12),border_radius=3)
        pygame.draw.rect(surf,(251,230,202),(31,19,3,3))
        pygame.draw.rect(surf,trim,(20,41,5,12))
        pygame.draw.rect(surf,tuple(min(255,c+30) for c in jacket),(32,38,4,4))
        if self.dash_time > 0 and not self.reduced_motion:
            for offset, alpha in ((12, 38), (22, 20)):
                echo = surf.copy()
                echo.set_alpha(alpha)
                self.screen.blit(echo, (int(center_x - 27 - offset), int(y - 74)))
        self.screen.blit(surf,(int(center_x-27),int(y-74)))

    def draw_ghost(self, sample: dict) -> None:
        """Draw a translucent, non-interactive character silhouette from replay data."""
        cx = int(self.lane_x(sample["lane"], PLAYER_Y))
        phase = max(0.0, min(1.0, 1.0 - float(sample.get("jump", 0)) / max(.01, self.jump_duration)))
        lift = int(54 * math.sin(math.pi * phase)) if sample.get("jump", 0) > 0 else 0
        base_y = PLAYER_Y - lift
        ghost = pygame.Surface((44, 68), pygame.SRCALPHA)
        tint = (90, 232, 246, 100 if not self.reduced_motion else 68)
        pygame.draw.ellipse(ghost, (28, 164, 196, 42), (4, 61, 36, 6))
        pygame.draw.rect(ghost, tint, (10, 43, 9, 18), border_radius=3)
        pygame.draw.rect(ghost, tint, (25, 43, 9, 18), border_radius=3)
        pygame.draw.rect(ghost, tint, (9, 25, 27, 24), border_radius=7)
        pygame.draw.rect(ghost, (150, 248, 255, 110), (14, 8, 17, 19), border_radius=7)
        pygame.draw.rect(ghost, (62, 154, 187, 120), (12, 5, 20, 8), border_radius=4)
        pygame.draw.line(ghost, tint, (10, 31), (4, 43), 5)
        pygame.draw.line(ghost, tint, (35, 31), (40, 41), 5)
        if sample.get("pose") == "slide":
            ghost = pygame.transform.rotate(ghost, -55)
        self.screen.blit(ghost, (cx - ghost.get_width()//2, base_y - ghost.get_height()))

    def animation_asset_key(self, state: str) -> str:
        """Choose the best available sprite animation for a character state."""
        aliases = {"idle":"run", "jump_prep":"jump", "fall":"jump", "landing":"run",
                   "dash":"run", "hit":"run", "shield":"run", "powerup":"run",
                   "defeat":"run", "victory":"run", "milestone":"run"}
        candidates = (state, aliases.get(state, "run"), "run")
        for candidate in candidates:
            key = f"{self.avatar_id}.{candidate}"
            if self.assets.has_animation(key):
                return key
        return f"{self.avatar_id}.{aliases.get(state, state)}"

    def draw_hud(self) -> None:
        """Render the score, lives, booster states, and dash meter."""
        self.panel((22,18,256,79), radius=18)
        self.text("SCORE",44,31,CYAN,self.small)
        self.text(f"{self.score:07d}",42,52,WHITE,self.huge)
        self.panel((704,18,234,79), radius=18)
        self.text("BEST  "+f"{self.best_score:07d}",724,31,MUTED,self.small)
        self.text("TOKEN",724,57,GOLD,self.small)
        self.text(f"{self.coins:03d}",815,52,WHITE,self.huge)
        self.panel((345,18,270,54), radius=16)
        for i in range(3):
            color = (83,230,170) if i >= self.hits else (252,95,140)
            x = 426 + i*48
            pygame.draw.polygon(self.screen,color,[(x,35),(x-12,25),(x-24,35),(x-22,49),(x,62),(x+22,49),(x+24,35),(x+12,25)])
        self.text(f"RUN LV {self.run_level}   PROFILE {self.profile_level}",480,79,GOLD,self.small,center=True)
        if self.shield:
            self.text(f"SHIELD x{self.shield}",359,91,GREEN,self.small)
        if self.magnet_time > 0:
            self.text(f"MAGNET {self.magnet_time:.0f}s",514,91,PINK,self.small)
        if self.score_boost_time > 0:
            self.text(f"2X {self.score_boost_time:.0f}s",480,92,GOLD,self.small,center=True)
        elif self.overdrive_time > 0:
            self.text(f"OVR {self.overdrive_time:.0f}s",480,92,CYAN,self.small,center=True)
        elif self.coin_bonus_time > 0:
            self.text(f"TOKEN 2X {self.coin_bonus_time:.0f}s",480,92,(255,145,70),self.small,center=True)
        if self.combo_enabled and self.combo.active:
            self.pill(f"CLEAN FLOW  x{self.combo.count}", (480, 126), GOLD)
        # Dash meter and explicit interaction prompt.
        self.panel((22,465,260,55), radius=14)
        self.text("DASH CHARGE",40,472,MUTED,self.small)
        pygame.draw.rect(self.screen,(35,48,68),(40,496,150,10),border_radius=5)
        pygame.draw.rect(self.screen,CYAN,(40,496,int(150*self.dash_charge/100),10),border_radius=5)
        ready = self.dash_charge >= 100
        self.text("E  DASH" if ready else "E  CHARGE",204,489,CYAN if ready else MUTED,self.small)
        self.panel((758,470,180,48),radius=14)
        self.text("P / ESC  PAUSE",780,486,MUTED,self.small)

    def draw_menu(self) -> None:
        """Render the title screen and main navigation."""
        # Title area deliberately leaves the track visible as a game preview.
        self.draw_track_preview()
        shade = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        shade.fill((5,8,19,130))
        self.screen.blit(shade,(0,0))
        self.panel((245,24,470,490),radius=28,outline=(41,75,101))
        self.text("AFTERHOURS  /  ARCADE",480,53,CYAN,self.small,center=True)
        self.text("NEON DASH",480,101,WHITE,self.title,center=True)
        self.text("Three lanes. One long night. Keep moving.",480,157,MUTED,self.body,center=True)
        labels=("START RUN","UPGRADES","CHOOSE RUNNER","HOW TO PLAY","COMFORT & CONTROLS","MISSIONS & RECORDS")
        for i,label in enumerate(labels):
            y=188+i*44
            active = i == self.menu_selection
            self.panel((322,y,316,38),radius=13,
                       fill=(25,68,91) if active else (21,29,49),
                       outline=CYAN if active else (48,60,81))
            self.text((">  " if active else "   ")+label,480,y+8,
                      WHITE if active else MUTED,self.font,center=True)
        self.text(f"LVL {self.profile_level}     UPGRADE PTS {self.upgrade_points}     BEST {self.best_score:07d}",480,467,GOLD,self.small,center=True)
        sound_label = "SOUND OFF" if self.audio.muted else "SOUND ON"
        self.text(f"W/S SELECT   ENTER CHOOSE   F11 FULLSCREEN   ESC QUIT   M {sound_label}",
                  480,494,MUTED,self.small,center=True)

    def draw_comfort(self) -> None:
        """Render accessibility and control settings."""
        self.draw_track_preview()
        shade = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        shade.fill((4, 8, 19, 178))
        self.screen.blit(shade, (0, 0))
        self.panel((172,26,616,490),radius=25,outline=(51,109,139))
        self.text("COMFORT & CONTROLS",480,58,CYAN,self.huge,center=True)
        if self.ghost_source == "archive" and self.ghost_archive:
            ghost_row = self.ghost_archive[self.ghost_archive_selection]
            ghost_label = f"RUN {ghost_row['run']}  {self.ghost_archive_selection+1}/{len(self.ghost_archive)}"
        else:
            ghost_label = self.ghost_source.upper()
        rows=(
            ("REDUCED MOTION", "Steadier track lights and less animation", "ON" if self.reduced_motion else "OFF"),
            ("CALM PACE", "Slower speed growth and more time to react", "ON" if self.calm_mode else "OFF"),
            ("MUSIC LEVEL", "Background music", ("OFF","SOFT","NORMAL","HIGH")[self.music_level]),
            ("EFFECTS LEVEL", "Quieter coins and power-up sounds", ("OFF","SOFT","NORMAL","HIGH")[self.sfx_level]),
            ("BLINK BREAK REMINDERS", "Gentle reminder about every four minutes", "ON" if self.break_reminders else "OFF"),
            ("TOUCH BUTTONS", "Show large tap controls during a run", "ON" if self.touch_controls else "OFF"),
            ("ADAPTIVE PACE", "Gradually tune difficulty to your play", self.adaptive.preference.upper()),
            ("GHOST RUNNER", "Best / previous / saved / off; arrows select run", ghost_label),
            ("REDUCE FLASHING", "Keep animated highlights steady", "ON" if self.reduced_flashing else "OFF"),
            ("SWIPE SENSITIVITY", "Gesture threshold", ("HIGH","NORMAL","LOW")[self.control_sensitivity]),
            ("CLEAN STREAK COMBOS", "Bonus points for consecutive clean actions", "ON" if self.combo_enabled else "OFF"),
            ("IMPACT SHAKE", "Small hit nudge; reduced motion disables it", "ON" if self.screen_shake_enabled else "OFF"),
            ("NEON GLOW", "Independent glow and bloom rendering", "ON" if self.glow_enabled else "OFF"),
            ("PICKUP PARTICLES", "Particle bursts and dash trails", "ON" if self.particles_enabled else "OFF"),
            ("TRACK REFLECTIONS", "Wet-road reflections and luminous streaks", "ON" if self.reflections_enabled else "OFF"),
            ("ATMOSPHERIC FX", "Rain, haze, fog and light shafts", "ON" if self.atmosphere_enabled else "OFF"),
        )
        for index,(label,description,value) in enumerate(rows):
            y=92+index*24
            active=index==self.comfort_selection
            self.panel((201,y,558,29),radius=9,fill=(24,51,70) if active else (17,28,47),outline=CYAN if active else (43,65,87))
            self.text(label,216,y,CYAN if active else WHITE,self.small)
            self.text(description,216,y+14,MUTED,self.small)
            self.text(value,708,y+7,GREEN if value in ("ON","SOFT") else GOLD,self.small,center=True)
        self.text("UP/DOWN SELECT   ENTER/CLICK CHANGE   ESC BACK",480,490,MUTED,self.small,center=True)

    def draw_touch_controls(self) -> None:
        """Render the optional touch-action buttons."""
        for cx,label in ((350,"LEFT"),(430,"JUMP"),(510,"SLIDE"),(590,"RIGHT"),(670,"DASH")):
            pygame.draw.circle(self.screen,(12,24,39),(cx,503),31)
            pygame.draw.circle(self.screen,(89,174,199),(cx,503),31,2)
            self.text(label,cx,503,WHITE,self.small,center=True)

    def draw_hub(self) -> None:
        """Render the missions and records navigation."""
        self.draw_track_preview()
        shade = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        shade.fill((4, 8, 19, 178))
        self.screen.blit(shade, (0, 0))
        self.panel((172,36,616,468),radius=25,outline=(51,109,139))
        self.text("NIGHT SHIFT RECORDS",480,75,CYAN,self.huge,center=True)
        labels=("MISSIONS", "ACHIEVEMENTS", "STATISTICS", "RUNNER PROFILE", "WORLDS", "CHALLENGE HISTORY")
        descriptions=("One-run goals and upgrade-point rewards",
                      "Lifetime milestones and one-time rewards",
                      "Distance, tokens, runs, and best result",
                      "Selected runner, level, wallet, and upgrades",
                      "Choose unlocked environments and view progression",
                      "Review locally saved daily and weekly rewards")
        for index,(label,description) in enumerate(zip(labels,descriptions)):
            y=112+index*60
            active=index==self.hub_selection
            self.panel((220,y,520,52),radius=12,fill=(24,51,70) if active else (17,28,47),outline=CYAN if active else (43,65,87))
            self.text(label,244,y+9,CYAN if active else WHITE,self.font)
            self.text(description,244,y+31,MUTED,self.small)
        self.text("UP/DOWN SELECT   ENTER OPEN   ESC BACK",480,487,MUTED,self.small,center=True)

    def draw_worlds(self) -> None:
        """Render the world selection preview and progression status."""
        world = WORLDS[self.world_selection]
        previous = self.world_id
        previous_level = self.profile_level
        self.world_id = world.key
        self.profile_level = max(previous_level, world.unlock_level)
        self.draw_track_preview()
        self.world_id = previous
        self.profile_level = previous_level
        shade = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        shade.fill((3, 7, 18, 165))
        self.screen.blit(shade, (0, 0))
        self.panel((210, 38, 540, 455), radius=25, outline=world.accent)
        self.text("WORLD SELECT", 480, 73, world.accent, self.huge, center=True)
        self.text(f"{self.world_selection + 1} / {len(WORLDS)}", 480, 112, GOLD, self.font, center=True)
        self.text(world.name, 480, 165, WHITE, self.title, center=True)
        self.text(world.atmosphere.upper() + " ATMOSPHERE", 480, 211, world.accent, self.body, center=True)
        self.text("HAZARDS  " + "  /  ".join(kind.replace("_", " ").upper() for kind in world.hazards),
                  480, 252, MUTED, self.small, center=True)
        unlocked = self.profile_level >= world.unlock_level
        status = "CURRENT WORLD" if world.key == previous else (
            "ENTER / CLICK TO SELECT" if unlocked else f"LOCKED  /  PROFILE LEVEL {world.unlock_level}")
        self.panel((300, 302, 360, 56), radius=14,
                   fill=(19, 55, 69) if unlocked else (34, 36, 50), outline=world.accent)
        self.text(status, 480, 319, GREEN if unlocked else GOLD, self.font, center=True)
        for index, item in enumerate(WORLDS):
            color = item.accent if index == self.world_selection else (67, 82, 101)
            pygame.draw.circle(self.screen, color, (440 + index * 20, 391), 5)
        self.text("A / D OR ARROWS BROWSE   ENTER / CLICK SELECT   ESC BACK",
                  480, 439, MUTED, self.small, center=True)
        self.text("<", 250, 329, world.accent, self.title, center=True)
        self.text(">", 710, 329, world.accent, self.title, center=True)

    def draw_challenge_history(self) -> None:
        """Render the completed daily and weekly challenge history."""
        goals = {goal.key: goal for goal in (*DAILY_CHALLENGES, *WEEKLY_CHALLENGES)}
        rows = []
        for item in reversed(self.challenge_history[-5:]):
            goal = goals.get(item["key"])
            if goal:
                rows.append((f"{item['period'].upper()}  /  {goal.title}", goal.detail,
                             f"COMPLETED  /  {item['date']}", True))
        if not rows:
            rows.append(("NO CHALLENGES COMPLETED", "Daily and weekly rewards appear here.",
                         "Keep running to start a record", False))
        self.draw_goal_page("CHALLENGE HISTORY", rows)

    def draw_missions(self) -> None:
        """Render active one-run and career missions."""
        rows=[]
        values={"distance":self.last_run_distance,"coins":self.last_run_coins,
                "dash_clears":self.last_run_dash_clears}
        values.update({key: self.last_run_metrics.get(key, 0) for key in
                       ("lane_changes", "jump_successes", "slide_successes", "near_misses", "elapsed")})
        values["powerup_count"] = (self.last_run_metrics.get("powerup_count")
                                     or sum(self.last_run_metrics.get("powerups", {}).values()))
        for goal in self.active_missions:
            done=goal.key in self.mission_ids
            progress=min(goal.target,values[goal.metric])
            status=f"CLAIMED  /  +{goal.reward} PTS" if done else f"LAST RUN  {progress}/{goal.target}   /   REWARD {goal.reward} PTS"
            rows.append((goal.title,goal.detail,status,done))
        for goal in self.active_career_missions:
            progress = min(goal.target, self.career_mission_progress[goal.key])
            rows.append((goal.title, goal.detail,
                         f"CAREER  {progress}/{goal.target}   /   REWARD {goal.reward} PTS",
                         goal.key in self.career_mission_ids))
        if not self.active_career_missions:
            rows.append(("CAREER CONTRACTS COMPLETE", "Every long-term contract is finished.",
                         "ALL CONTRACT REWARDS EARNED", True))
        daily_progress=min(self.daily_goal.target, values[self.daily_goal.metric])
        daily_status=(f"TODAY CLAIMED  /  +{self.daily_goal.reward} PTS" if self.daily_claimed
                      else f"TODAY  {daily_progress}/{self.daily_goal.target}   /   REWARD {self.daily_goal.reward} PTS")
        rows.append((self.daily_goal.title,self.daily_goal.detail,daily_status,self.daily_claimed))
        weekly_value = min(self.weekly_goal.target, self.weekly_progress[self.weekly_goal.metric])
        weekly_status = (f"THIS WEEK CLAIMED  /  +{self.weekly_goal.reward} PTS" if self.weekly_claimed
                         else f"THIS WEEK  {weekly_value}/{self.weekly_goal.target}   /   REWARD {self.weekly_goal.reward} PTS")
        rows.append((self.weekly_goal.title,self.weekly_goal.detail,weekly_status,self.weekly_claimed))
        self.draw_goal_page("MISSIONS & CONTRACTS",rows)

    def draw_achievements(self) -> None:
        """Render lifetime achievement progress."""
        stats={"total_runs":self.total_runs,"lifetime_distance":self.lifetime_distance,
               "lifetime_coins":self.lifetime_coins,"lifetime_dash_clears":self.lifetime_dash_clears}
        rows=[]
        for goal in ACHIEVEMENTS:
            progress=min(goal.target,stats[goal.metric])
            done=goal.key in self.achievement_ids
            status=f"UNLOCKED  /  +{goal.reward} PTS" if done else f"{progress}/{goal.target}   /   REWARD {goal.reward} PTS"
            rows.append((goal.title,goal.detail,status,done))
        self.draw_goal_page("ACHIEVEMENTS",rows)

    def draw_goal_page(self,title:str,rows:list[tuple[str,str,str,bool]])->None:
        """Render a page of progress goals and their completion status."""
        self.draw_track_preview()
        shade = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        shade.fill((4, 8, 19, 184))
        self.screen.blit(shade, (0, 0))
        self.panel((145,30,670,480),radius=25,outline=(51,109,139))
        self.text(title,480,65,CYAN,self.huge,center=True)
        compact = len(rows) > 5
        for index,(label,detail,status,done) in enumerate(rows):
            y=(100+index*51) if compact else (108+index*70)
            card_height = 50 if compact else 64
            self.panel((178,y,604,card_height),radius=13,
                       fill=(22,53,63) if done else (17,28,47),outline=GREEN if done else (43,65,87))
            self.text(label,198,y+(2 if compact else 7),WHITE,self.font)
            self.text(detail,198,y+(20 if compact else 31),MUTED,self.small)
            self.text(status,480,y+(43 if compact else 53),GREEN if done else GOLD,
                      self.small,center=True)
        self.text("ESC / BACKSPACE / CLICK BELOW TO BACK",480,480,MUTED,self.small,center=True)

    def draw_statistics(self) -> None:
        """Render recent and lifetime run statistics."""
        recent = self.analytics.runs[-5:]
        jump_count = sum(run.get("jumps", 0) for run in recent)
        jump_success = sum(run.get("jump_successes", 0) for run in recent)
        slide_count = sum(run.get("slides", 0) for run in recent)
        slide_success = sum(run.get("slide_successes", 0) for run in recent)
        average_survival = (sum(run.get("elapsed", 0) for run in recent) / len(recent)
                            if recent else 0)
        self.draw_info_page("RUN STATISTICS",(
            ("TOTAL RUNS",f"{self.total_runs:,}"),
            ("BEST SCORE",f"{self.best_score:,}"),
            ("BEST TOKENS IN A RUN",f"{self.best_coins:,}"),
            ("LIFETIME DISTANCE",f"{self.lifetime_distance:,} m"),
            ("LIFETIME TOKENS",f"{self.lifetime_coins:,}"),
            ("LIFETIME COLLISIONS",f"{self.analytics.totals['collisions']:,}"),
            ("DASHED HAZARDS",f"{self.lifetime_dash_clears:,}"),
            ("RECENT JUMP ACCURACY",f"{jump_success}/{jump_count}" if jump_count else "NO JUMP DATA"),
            ("RECENT SLIDE ACCURACY",f"{slide_success}/{slide_count}" if slide_count else "NO SLIDE DATA"),
            ("AVG SURVIVAL / LAST 5",f"{average_survival:.1f} sec"),
            ("PREFERRED LANE",("LEFT","CENTER","RIGHT")[self.analytics.preferred_lane]),
        ))

    def draw_profile(self) -> None:
        """Render the runner profile and progression details."""
        self.draw_info_page("RUNNER PROFILE",(
            ("SELECTED RUNNER",self.avatar_id.upper()),
            ("PROFILE LEVEL",str(self.profile_level)),
            ("PROFILE XP",f"{self.profile_xp:,} / {self.profile_level*5000:,}"),
            ("UPGRADE POINTS",f"{self.upgrade_points:,}"),
            ("UPGRADES PURCHASED",str(sum(self.upgrades.values()))),
            ("RUNNER COLLECTION",f"{len(self.unlocked_avatars)} / {len(AVATARS)}"),
        ))

    def draw_info_page(self,title:str,rows:tuple[tuple[str,str],...])->None:
        """Render a titled list of profile information rows."""
        self.draw_track_preview()
        shade = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        shade.fill((4, 8, 19, 184))
        self.screen.blit(shade, (0, 0))
        self.panel((185,25,590,490),radius=25,outline=(51,109,139))
        self.text(title,480,60,CYAN,self.huge,center=True)
        for index,(label,value) in enumerate(rows):
            spacing = min(37, 340 / max(1, len(rows)-1))
            y=int(100+index*spacing)
            self.panel((220,y,520,36),radius=10,fill=(17,28,47),outline=(43,65,87))
            self.text(label,239,y+9,MUTED,self.small)
            self.text(value,699,y+7,WHITE,self.small,center=False)
        self.text("ESC / BACKSPACE / CLICK BELOW TO BACK",480,481,MUTED,self.small,center=True)

    def draw_upgrades(self) -> None:
        """Render the upgrade shop and available purchases."""
        self.draw_track_preview()
        shade = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        shade.fill((4, 8, 19, 176))
        self.screen.blit(shade, (0, 0))
        self.panel((172,26,616,490),radius=25,outline=(51,109,139))
        self.text("NEON GARAGE",480,54,CYAN,self.huge,center=True)
        self.text(f"UPGRADE POINTS  {self.upgrade_points}",480,91,GOLD,self.body,center=True)
        for index,(key,label,description,maximum) in enumerate(UPGRADES):
            y=118+index*70
            active=index==self.upgrade_selection
            self.panel((205,y,550,60),radius=13,fill=(24,51,70) if active else (17,28,47),outline=CYAN if active else (43,65,87))
            level=self.upgrades.get(key,0)
            cost="MAX" if level>=maximum else f"COST {self.upgrade_cost(key)}"
            self.text(f"{label}   LV {level}/{maximum}",225,y+8,CYAN if active else WHITE,self.font)
            self.text(description,225,y+34,MUTED,self.small)
            self.text(cost,617,y+19,GOLD if level<maximum else GREEN,self.small,center=True)
        if self.message_timer > 0:
            self.text(self.message,480,467,GOLD,self.small,center=True)
        else:
            self.text("UP/DOWN SELECT   ENTER BUY   CLICK HERE TO BACK",480,483,MUTED,self.small,center=True)

    def draw_avatars(self) -> None:
        """Render runner selection and unlock information."""
        self.draw_track_preview()
        shade = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        shade.fill((4, 8, 19, 176))
        self.screen.blit(shade, (0, 0))
        self.panel((205,28,550,486),radius=25,outline=(51,109,139))
        avatar=AVATARS[self.avatar_selection]
        self.text("RUNNER SELECT",480,58,CYAN,self.huge,center=True)
        self.text("A / D OR LEFT / RIGHT TO BROWSE",480,101,MUTED,self.small,center=True)
        self.draw_avatar_preview(avatar,480,255)
        self.text(avatar["name"],480,354,WHITE,self.title,center=True)
        self.text(avatar["tag"],480,395,avatar["trim"],self.body,center=True)
        unlocked=avatar["id"] in self.unlocked_avatars
        if unlocked and avatar["id"]==self.avatar_id:
            action="CURRENT RUNNER"
        elif unlocked:
            action="ENTER  SELECT RUNNER"
        else:
            action=f"ENTER  UNLOCK FOR {avatar['cost']} POINTS"
        self.panel((310,430,340,48),radius=13,fill=(22,61,82),outline=CYAN)
        self.text(action,480,443,WHITE,self.font,center=True)
        if self.message_timer > 0:
            self.text(self.message,480,482,GOLD,self.small,center=True)
        else:
            self.text(f"WALLET  {self.upgrade_points} PTS   /   CLICK BELOW TO BACK",480,494,GOLD,self.small,center=True)

    def draw_avatar_preview(self,avatar:dict,x:int,y:int)->None:
        """Render the procedural preview for one runner."""
        jacket,trim,hair=avatar["jacket"],avatar["trim"],avatar["hair"]
        pygame.draw.ellipse(self.screen,(3,6,14),(x-54,y+112,108,20))
        pygame.draw.rect(self.screen,(24,28,45),(x-31,y+76,24,48),border_radius=7)
        pygame.draw.rect(self.screen,(24,28,45),(x+7,y+76,24,48),border_radius=7)
        pygame.draw.rect(self.screen,jacket,(x-38,y+119,38,9),border_radius=4)
        pygame.draw.rect(self.screen,jacket,(x+1,y+119,38,9),border_radius=4)
        pygame.draw.rect(self.screen,(40,48,77),(x-43,y+28,86,58),border_radius=17)
        pygame.draw.rect(self.screen,jacket,(x-35,y+34,70,39),border_radius=10)
        pygame.draw.rect(self.screen,trim,(x-27,y+46,9,23),border_radius=3)
        pygame.draw.rect(self.screen,(240,184,146),(x-23,y-23,46,51),border_radius=16)
        pygame.draw.rect(self.screen,hair,(x-28,y-31,56,24),border_radius=12)
        pygame.draw.rect(self.screen,hair,(x-31,y-18,13,22),border_radius=6)
        pygame.draw.rect(self.screen,(37,32,42),(x+5,y-1,5,5))
        pygame.draw.rect(self.screen,WHITE,(x+22,y+34,7,7))

    def draw_track_preview(self) -> None:
        """Render a decorative gameplay track for menu previews."""
        self.draw_run_background_only()
        # Decorative electric street cars and a few floating tokens.
        for lane in (0,2):
            x=self.lane_x(lane,340)
            pygame.draw.rect(self.screen,(30,46,72),(int(x-34),300,68,86),border_radius=18)
            pygame.draw.rect(self.screen,(78,129,158),(int(x-25),311,50,33),border_radius=11)
            pygame.draw.rect(self.screen,(25,39,59),(int(x-18),316,36,18),border_radius=6)
            pygame.draw.line(self.screen,CYAN,(int(x-18),368),(int(x+18),368),4)
            pygame.draw.circle(self.screen,GOLD,(int(x-21),373),4)
            pygame.draw.circle(self.screen,GOLD,(int(x+21),373),4)
        for x,y in ((410,360),(480,315),(550,360)):
            pygame.draw.circle(self.screen,GOLD,(x,y),10)

    def draw_run_background_only(self) -> None:
        """Render the city and track without active game entities."""
        # Reuse city dressing; road is kept unoccupied in the title preview.
        self.draw_city()
        pygame.draw.polygon(self.screen,(17,24,39),[(422,150),(538,150),(910,540),(50,540)])
        for side in (-1,1):
            pygame.draw.line(self.screen,(66,100,123),(480+side*58,150),(480+side*420,540),3)
        for boundary in (-.5,.5):
            pygame.draw.line(self.screen,(60,72,94),(480+boundary*40,150),(480+boundary*121,540),2)

    def draw_tutorial(self) -> None:
        """Render the current tutorial page."""
        self.draw_track_preview()
        shade = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        shade.fill((5,8,19,165))
        self.screen.blit(shade,(0,0))
        self.panel((170,50,620,445),radius=24,outline=CYAN)
        self.text("QUICK START",480,77,CYAN,self.small,center=True)
        titles=("MOVE BETWEEN LANES","JUMP OR SLIDE","PICK UP & POWER UP")
        subtitles=("Change lanes to dodge electric cars and find clear paths.",
                   "Jump the ion barricades. Slide beneath the charged laser gates.",
                   "Collect tokens and energy. Shield blocks a hit; magnet pulls tokens.")
        self.text(f"{self.tutorial_page+1} / 3",480,117,GOLD,self.small,center=True)
        self.text(titles[self.tutorial_page],480,153,WHITE,self.huge,center=True)
        self.text(subtitles[self.tutorial_page],480,211,MUTED,self.body,center=True)
        if self.tutorial_page == 0:
            self.control_card(255,277,"A","LEFT LANE",CYAN)
            self.control_card(410,277,"S","SLIDE",PINK)
            self.control_card(565,277,"D","RIGHT LANE",CYAN)
            self.text("Touch: swipe left/right to change lanes; swipe up to jump.",480,371,MUTED,self.small,center=True)
        elif self.tutorial_page == 1:
            self.control_card(310,277,"W / SPACE","JUMP",GOLD)
            self.control_card(505,277,"S","SLIDE",PINK)
        else:
            self.control_card(310,277,"E","DASH AT FULL METER",CYAN)
            self.control_card(505,277,"P","PAUSE ANYTIME",MUTED)
        self.text("Three hearts. The run ends only after three crashes.",480,387,GOLD,self.small,center=True)
        self.panel((350,424,260,48),radius=14,fill=(23,65,86),outline=CYAN)
        self.text("ENTER / SPACE  NEXT",480,437,WHITE,self.font,center=True)
        self.text("ESC  BACK TO TITLE",480,485,MUTED,self.small,center=True)

    def control_card(self,x:int,y:int,key:str,label:str,color:tuple[int,int,int])->None:
        """Render a tutorial card for one control."""
        self.panel((x,y,140,82),radius=14,fill=(17,28,48),outline=(54,72,97))
        self.text(key,x+70,y+12,color,self.body,center=True)
        self.text(label,x+70,y+52,MUTED,self.small,center=True)

    def draw_pause(self) -> None:
        """Render the pause overlay."""
        self.overlay_card("PAUSED", "Take a moment. Resume when you are ready.",
                          "ENTER / R  RESUME RUN", "U  UPGRADES     C  RUNNER     Q  TITLE")

    def draw_gameover(self) -> None:
        """Render the game-over summary and run statistics."""
        self.overlay_card("RUN OVER", f"{self.score:,} SCORE   /   {self.coins} TOKENS   /   +{self.coins} UPGRADE PTS",
                          "ENTER / R  RUN IT BACK", f"BEST {self.best_score:,}   U UPGRADES   ESC TITLE")
        powerups = sum(self.telemetry.powerups.values())
        accuracy = (f"JUMP {self.telemetry.jump_successes}/{self.telemetry.jumps}  "
                    f"SLIDE {self.telemetry.slide_successes}/{self.telemetry.slides}")
        self.text(f"{int(self.distance):,}m / {self.elapsed:.0f}s / HITS {self.telemetry.collision_count} / "
                  f"{accuracy} / DASH {self.telemetry.dash_activations} / BOOSTERS {powerups}",
                  480, 393, WHITE, self.small, center=True)
        record = "NEW PERSONAL BEST!" if self.score > getattr(self, "previous_best_score", 0) else \
            f"PERSONAL BEST GAP  {self.best_score - self.score:,}"
        self.text(record + "  /  " + self.analytics.coach(), 480, 416, MUTED, self.small, center=True)

    def overlay_card(self,title:str,subtitle:str,primary:str,secondary:str)->None:
        """Render a modal card with its title and action prompts."""
        shade = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        shade.fill((4, 7, 18, 175))
        self.screen.blit(shade, (0, 0))
        self.panel((260,130,440,300),radius=26,outline=CYAN)
        self.text(title,480,165,WHITE,self.huge,center=True)
        self.text(subtitle,480,228,MUTED,self.body,center=True)
        self.panel((330,290,300,54),radius=14,fill=(24,67,89),outline=CYAN)
        self.text(primary,480,305,WHITE,self.font,center=True)
        self.text(secondary,480,371,MUTED,self.small,center=True)

    def panel(self,rect:tuple[int,int,int,int],radius:int=12,
              fill:tuple[int,int,int]=(13,20,38),outline:tuple[int,int,int]|None=None)->None:
        """Draw a panel with an optional outline."""
        x, y, width, height = rect
        edge = outline or (52, 83, 109)
        surface = panel_surface(width, height, fill, edge)
        self.screen.blit(surface, (x, y))

    def pill(self,label:str,center:tuple[int,int],color:tuple[int,int,int])->None:
        """Draw a centered status label."""
        surf=self.font.render(label,True,WHITE)
        rect=surf.get_rect(center=center).inflate(30,17)
        self.panel((rect.x, rect.y, rect.width, rect.height), 12,
                   fill=(12,20,36), outline=color)
        self.screen.blit(surf,surf.get_rect(center=center))

    def text(self,label:str,x:float,y:float,color:tuple[int,int,int],font:pygame.font.Font,  # pylint: disable=too-many-arguments,too-many-positional-arguments
             center:bool=False)->None:
        """Render text at the requested screen position."""
        surface=font.render(label,True,color)
        rect=surface.get_rect()
        if center:
            rect.center=(int(x),int(y))
        else:
            rect.topleft=(int(x),int(y))
        self.screen.blit(surface,rect)


if __name__ == "__main__":
    NeonRunner().run()
