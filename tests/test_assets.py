import json
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from engine.assets import AnimatedSprite, AssetPack


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
