import json
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from engine.assets import AnimatedSprite, AssetPack
from engine.svg_art import (entity_surface, road_surface, runner_surface,
                            scaled as scale_svg)


def test_python_package_asset_pack_loads_animation_sprite_and_backdrop(tmp_path, monkeypatch):
    pygame.init()
    pygame.display.set_mode((1, 1))
    package = tmp_path / "sample_game_art"
    content = package / "art"
    content.mkdir(parents=True)
    (package / "__init__.py").write_text("", encoding="utf-8")
    atlas = pygame.Surface((32, 16), pygame.SRCALPHA)
    atlas.fill((245, 32, 64, 255), pygame.Rect(0, 0, 16, 16))
    atlas.fill((32, 224, 180, 255), pygame.Rect(16, 0, 16, 16))
    pygame.image.save(atlas, content / "atlas.png")
    manifest = {
        "textures": {"atlas": "atlas.png"},
        "animations": {"nova.run": {
            "texture": "atlas", "fps": 2, "loop": False,
            "frames": [[0, 0, 16, 16], [16, 0, 16, 16]],
        }},
        "sprites": {"coin": {"texture": "atlas", "frame": [0, 0, 16, 16]}},
        "backgrounds": {"city": "atlas"},
    }
    (content / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.setenv("NEON_DASH_ASSET_PACK", "sample_game_art:art/manifest.json")

    try:
        pack = AssetPack.from_environment()
        animation = AnimatedSprite(pack, "nova.run")
        animation.update(1.0)
        assert animation.image.get_at((0, 0))[:3] == (32, 224, 180)
        assert pack.sprite("coin").get_at((0, 0))[:3] == (245, 32, 64)
        assert pack.background("city").get_size() == (32, 16)
    finally:
        pygame.quit()


def test_missing_asset_package_falls_back_to_empty_pack(monkeypatch):
    monkeypatch.setenv("NEON_DASH_ASSET_PACK", "missing_art_package:manifest.json")
    pack = AssetPack.from_environment()
    assert pack.frame("nova.run", 0) is None


def test_malformed_manifest_sections_are_ignored():
    pack = AssetPack({"textures": [], "animations": "bad", "sprites": None,
                      "backgrounds": 12})
    assert pack.frame("nova.run", 0) is None
    assert pack.sprite("coin") is None
    assert pack.background("city") is None


def test_atlas_frames_and_scaled_images_are_cached():
    pygame.init()
    atlas = pygame.Surface((8, 8), pygame.SRCALPHA)
    pack = AssetPack({"textures": {"atlas": "unused.png"},
                      "animations": {"runner.run": {"texture": "atlas", "frames": [[0, 0, 8, 8]]}}})
    pack.textures["atlas"] = atlas
    first = pack.frame("runner.run", 0)
    second = pack.frame("runner.run", .01)
    assert first is second
    assert pack.scaled(first, (24, 24)) is pack.scaled(second, (24, 24))
    for edge in range(1, 140):
        pack.scaled(first, (edge, edge))
    assert len(pack._scaled) == 128
    pygame.quit()


def test_svg_assets_load_from_manifest_and_reuse_vector_surfaces(tmp_path):
    pygame.init()
    pygame.display.set_mode((1, 1))
    (tmp_path / "vector.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" '
        'viewBox="0 0 16 16"><circle cx="8" cy="8" r="6" fill="#40eaff"/></svg>',
        encoding="utf-8",
    )
    pack = AssetPack({"textures": {"icon": "vector.svg"},
                      "sprites": {"icon": "icon"}}, root=tmp_path)
    try:
        image = pack.sprite("icon")
        assert image is not None
        assert image.get_size() == (16, 16)
        assert image.get_at((8, 8))[:3] == (64, 234, 255)
        assert image.get_at((0, 0)).a == 0
        assert scale_svg(image, (32, 32)) is scale_svg(image, (32, 32))
        assert entity_surface("coin").get_size() == (96, 96)
        runner_frame_0 = runner_surface((49, 222, 224), (255, 117, 134),
                                        (29, 29, 48), "run", 0)
        runner_frame_1 = runner_surface((49, 222, 224), (255, 117, 134),
                                        (29, 29, 48), "run", 1)
        assert runner_frame_0.get_size() == (88, 88)
        assert any(
            runner_frame_0.get_at((x, y)) != runner_frame_1.get_at((x, y))
            for x in range(15, 76)
            for y in range(58, 84)
        )
        road_0 = road_surface((18, 24, 40), (49, 225, 232), 3)
        assert road_0.get_size() == (960, 540)
        assert road_surface((18, 24, 40), (49, 225, 232), 3) is road_0
        road_no_reflections = road_surface((18, 24, 40), (49, 225, 232),
                                           3, reflections=False)
        assert road_no_reflections is not road_0
    finally:
        pygame.quit()


def test_white_box_svg_entity_pose_loop_and_cache_branches():
    pygame.init()
    try:
        pygame.display.set_mode((960, 540))
        from engine.svg_art import (glow_surface, panel_surface, scaled,
                                    sky_surface, skyline_surface)

        sky_surface.cache_clear()
        first_sky = sky_surface((18, 31, 56), (63, 231, 235))
        assert sky_surface((18, 31, 56), (63, 231, 235)) is first_sky
        sky_surface((33, 20, 60), (255, 84, 155))

        building_specs = ((0, 60, 80, 0), (65, 45, 120, 1),
                          (115, 70, 45, 2))
        first_skyline = skyline_surface(building_specs, 960, 275,
                                        ((18, 31, 56), (63, 231, 235)))
        assert skyline_surface(building_specs, 960, 275,
                               ((18, 31, 56), (63, 231, 235))) is first_skyline

        known_entities = (
            "coin", "battery", "shield", "magnet", "score_boost",
            "overdrive", "coin_bonus", "barrier", "gate", "fence",
            "electric_car", "train",
        )
        for kind in known_entities:
            assert entity_surface(kind) is not None
        assert entity_surface("unknown_entity") is None

        for pose in ("run", "jump", "slide", "shield", "dash", "fall"):
            for frame in (0, 1, 7, 8):
                art = runner_surface((-40, 300, 520), (-20, 400, 600),
                                     (-10, 200, 300), pose, frame)
                assert art is not None

        assert panel_surface(12, 12, (13, 20, 38), (63, 231, 235)).get_size() == (12, 12)
        assert panel_surface(320, 160, (13, 20, 38), (63, 231, 235)).get_size() == (320, 160)
        assert glow_surface((255, 84, 155), 4).get_size() == (4, 4)
        assert glow_surface((255, 84, 155), 128).get_size() == (128, 128)

        from engine.svg_art import _SCALED
        test_surface = pygame.Surface((8, 8), pygame.SRCALPHA)
        for edge in range(-5, 140):
            scaled(test_surface, (edge, edge))
        assert len(_SCALED) <= 128
    finally:
        pygame.quit()


def test_missing_animation_clears_previous_sprite_image():
    pygame.init()
    atlas = pygame.Surface((8, 8), pygame.SRCALPHA)
    pack = AssetPack({
        "textures": {"atlas": "atlas.png"},
        "animations": {"runner.run": {
            "texture": "atlas", "frames": [[0, 0, 8, 8]],
        }},
    })
    pack.textures["atlas"] = atlas
    sprite = AnimatedSprite(pack, "runner.run")
    assert sprite.image is not None
    sprite.set_animation("violet.jump")
    assert sprite.image is None
    pygame.quit()
