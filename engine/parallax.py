"""Lightweight deterministic pixel skyline layers for the endless track."""

from __future__ import annotations

import random

import pygame

from engine.svg_art import skyline_surface


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
        artwork = skyline_surface(tuple(self.buildings), self.TILE_WIDTH, self.base_y,
                                  (skyline_color, accent))
        for tile_x in (-self.TILE_WIDTH, 0, self.TILE_WIDTH):
            tile_origin = tile_x - int(offset)
            if tile_origin >= target.get_width() or tile_origin + self.TILE_WIDTH < 0:
                continue
            target.blit(artwork, (tile_origin, 0))


def make_city_layers() -> tuple[SkylineLayer, SkylineLayer]:
    """Return distant and middle strips; foreground art remains game-owned."""
    return (SkylineLayer(818, .012, (28, 84)),
            SkylineLayer(1999, .035, (54, 132)))
