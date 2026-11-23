"""Lightweight deterministic pixel skyline layers for the endless track."""

from __future__ import annotations

import random

import pygame


class SkylineLayer:
    """A repeating skyline strip that scrolls at its own depth speed."""

    TILE_WIDTH = 1600

    def __init__(self, seed: int, depth: float, height_range: tuple[int, int],
                 base_y: int = 275) -> None:
        self.depth = depth
        self.base_y = base_y
        self._offset = 0.0
        rng = random.Random(seed)
        self.buildings: list[tuple[int, int, int, int]] = []
        x = 0
        while x < self.TILE_WIDTH:
            width = rng.randrange(28, 76)
            height = rng.randrange(height_range[0], height_range[1] + 1)
            self.buildings.append((x, width, height, rng.randrange(3)))
            x += width + rng.randrange(7, 20)

    @property
    def offset(self) -> float:
        """Most recent offset, set by draw for inspection/debug overlays."""
        return self._offset

    def draw(self, target: pygame.Surface, distance: float,
             skyline_color: tuple[int, int, int], accent: tuple[int, int, int],
             reduced_motion: bool = False) -> None:
        """Draw the repeating skyline at its distance-based scroll position."""
        offset = 0.0 if reduced_motion else (max(0.0, distance) * self.depth) % self.TILE_WIDTH
        self._offset = offset
        base_color = tuple(max(0, min(255, round(channel * .68))) for channel in skyline_color)
        for tile_x in (-self.TILE_WIDTH, 0, self.TILE_WIDTH):
            tile_origin = tile_x - int(offset)
            if tile_origin >= target.get_width() or tile_origin + self.TILE_WIDTH < 0:
                continue
            for x, width, height, style in self.buildings:
                left = tile_origin + x
                if left + width < 0 or left > target.get_width():
                    continue
                top = self.base_y - height
                shade = .78 + style * .08
                color = tuple(min(255, int(channel * shade)) for channel in base_color)
                pygame.draw.rect(target, color, (left, top, width, height))
                if style == 1:
                    pygame.draw.rect(target, color, (left + width // 3, top - 7, width // 3, 8))
                # A few restrained window pixels establish scale without
                # competing with the detailed foreground buildings.
                for wx in range(left + 7, left + width - 4, 15):
                    for wy in range(top + 10, self.base_y - 7, 20):
                        if (wx * 11 + wy * 5) % 4:
                            pixel = tuple((a + b) // 3 for a, b in zip(accent, color))
                            pygame.draw.rect(target, pixel, (wx, wy, 3, 5))


def make_city_layers() -> tuple[SkylineLayer, SkylineLayer]:
    """Return distant and middle strips; foreground art remains game-owned."""
    return (SkylineLayer(818, .012, (28, 84)),
            SkylineLayer(1999, .035, (54, 132)))
