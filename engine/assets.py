"""Load replaceable sprite and backdrop packs from files or Python packages.

Pack manifest format::

    {"textures": {"runner": "sprites/runner.png"},
     "animations": {"nova.run": {"texture": "runner", "fps": 10,
                     "frames": [[0, 0, 32, 48], [32, 0, 32, 48]]}},
     "sprites": {"coin": {"texture": "runner", "frame": [0, 48, 16, 16]}},
     "backgrounds": {"city": "backgrounds/city.png"}}

Set NEON_DASH_ASSET_PACK to a manifest path or ``python_package:resource/path``.
Package data can then ship beside an installable Python game-art package.
"""

from __future__ import annotations

from collections import OrderedDict
from importlib import resources
from io import BytesIO
import json
import math
import os
from pathlib import Path
from typing import Any

import pygame


class AssetPack:
    """Cached image, sprite-sheet and animation access for the renderer."""

    def __init__(self, manifest: dict[str, Any] | None = None,
                 root: Path | None = None, package: str | None = None,
                 resource_root: str = "") -> None:
        self.manifest = manifest or {}
        self.root = root
        self.package = package
        self.resource_root = resource_root.strip("/")
        self.textures: dict[str, pygame.Surface] = {}
        self._frames: dict[tuple[str, tuple[int, int, int, int]], pygame.Surface] = {}
        self._scaled: OrderedDict[tuple[int, tuple[int, int]], pygame.Surface] = OrderedDict()
        self._texture_paths = self._mapping("textures")
        self._animations = self._mapping("animations")
        self._sprites = self._mapping("sprites")
        self._backgrounds = self._mapping("backgrounds")

    def _mapping(self, key: str) -> dict[str, Any]:
        value = self.manifest.get(key, {})
        return value if isinstance(value, dict) else {}

    @classmethod
    def from_environment(cls) -> "AssetPack":
        """Load a filesystem or package pack, falling back cleanly when unset."""
        source = os.environ.get("NEON_DASH_ASSET_PACK", "").strip()
        if not source:
            return cls()
        try:
            if ":" in source and not Path(source).exists():
                package, manifest_name = source.split(":", 1)
                resource_path = Path(manifest_name)
                manifest_bytes = (resources.files(package)
                                  .joinpath(*resource_path.parts).read_bytes())
                manifest = json.loads(manifest_bytes)
                if not isinstance(manifest, dict):
                    return cls()
                return cls(manifest, package=package,
                           resource_root=resource_path.parent.as_posix())
            manifest_path = Path(source).expanduser().resolve()
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if not isinstance(manifest, dict):
                return cls()
            return cls(manifest, root=manifest_path.parent)
        except (OSError, ValueError, ImportError, ModuleNotFoundError):
            return cls()

    def _read(self, relative: str) -> bytes:
        if self.package:
            target = Path(self.resource_root, relative)
            return resources.files(self.package).joinpath(*target.parts).read_bytes()
        if self.root:
            return (self.root / relative).read_bytes()
        raise FileNotFoundError("No asset pack is configured")

    def texture(self, name: str) -> pygame.Surface | None:
        if name in self.textures:
            return self.textures[name]
        relative = self._texture_paths.get(name)
        if not relative:
            return None
        try:
            image = pygame.image.load(BytesIO(self._read(relative)), relative)
            image = image.convert_alpha() if pygame.display.get_surface() else image
        except (OSError, pygame.error, ValueError, TypeError):
            return None
        self.textures[name] = image
        return image

    def _crop(self, texture_name: str, frame: list[int] | tuple[int, ...]) -> pygame.Surface | None:
        texture = self.texture(texture_name)
        if texture is None or not isinstance(frame, (tuple, list)) or len(frame) != 4:
            return None
        try:
            rect_values = tuple(int(value) for value in frame)
            rect = pygame.Rect(rect_values)
        except (TypeError, ValueError, OverflowError):
            return None
        if rect.width <= 0 or rect.height <= 0 or not texture.get_rect().contains(rect):
            return None
        key = (texture_name, rect_values)
        if key not in self._frames:
            self._frames[key] = texture.subsurface(rect).copy()
        return self._frames[key]

    def scaled(self, image: pygame.Surface, size: tuple[int, int]) -> pygame.Surface:
        """Scale a cached source surface once for each requested display size."""
        size = (max(1, int(size[0])), max(1, int(size[1])))
        key = (id(image), size)
        if key not in self._scaled:
            self._scaled[key] = pygame.transform.scale(image, size)
            if len(self._scaled) > 128:
                self._scaled.popitem(last=False)
        else:
            self._scaled.move_to_end(key)
        return self._scaled[key]

    def frame(self, animation_name: str, elapsed: float) -> pygame.Surface | None:
        """Get the animation frame at elapsed seconds, clamped for one-shots."""
        animation = self._animations.get(animation_name)
        if not isinstance(animation, dict):
            return None
        frames = animation.get("frames", ())
        if not isinstance(frames, (tuple, list)) or not frames:
            return None
        try:
            fps = max(0.01, float(animation.get("fps", 10)))
        except (TypeError, ValueError, OverflowError):
            fps = 10.0
        safe_elapsed = max(0.0, elapsed) if math.isfinite(elapsed) else 0.0
        index = int(safe_elapsed * fps)
        if animation.get("loop", True):
            index %= len(frames)
        else:
            index = min(index, len(frames) - 1)
        return self._crop(animation.get("texture", ""), frames[index])

    def has_animation(self, animation_name: str) -> bool:
        """Whether the manifest defines a usable animation entry for this name."""
        entry = self._animations.get(animation_name)
        return isinstance(entry, dict) and bool(entry.get("frames"))

    def sprite(self, name: str) -> pygame.Surface | None:
        item = self._sprites.get(name)
        if not isinstance(item, (dict, str)):
            return None
        if isinstance(item, str):
            return self.texture(item)
        return self._crop(item.get("texture", ""), item.get("frame", ()))

    def background(self, name: str) -> pygame.Surface | None:
        source = self._backgrounds.get(name)
        if not isinstance(source, (dict, str)):
            return None
        if isinstance(source, str):
            return self.texture(source)
        return self._crop(source.get("texture", ""), source.get("frame", ()))


class AnimatedSprite(pygame.sprite.Sprite):
    """Pygame Sprite driven by a named animation in an :class:`AssetPack`."""

    def __init__(self, pack: AssetPack, animation: str = "") -> None:
        super().__init__()
        self.pack = pack
        self.animation = ""
        self.elapsed = 0.0
        self.image: pygame.Surface | None = None
        self.rect = pygame.Rect(0, 0, 0, 0)
        self.set_animation(animation)

    def set_animation(self, animation: str) -> None:
        if animation != self.animation:
            self.animation = animation
            self.elapsed = 0.0
            self._select_frame()

    def restart(self) -> None:
        """Restart the selected one-shot without changing its manifest key."""
        self.elapsed = 0.0
        self._select_frame()

    def update(self, dt: float = 0.0) -> None:
        self.elapsed += max(0.0, dt)
        self._select_frame()

    def _select_frame(self) -> None:
        image = self.pack.frame(self.animation, self.elapsed) if self.animation else None
        self.image = image
        if image is not None:
            self.rect.size = image.get_size()
        else:
            self.rect.size = (0, 0)
