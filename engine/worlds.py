"""Offline environment catalog with level unlocks and procedural palettes."""

from dataclasses import dataclass


@dataclass(frozen=True)
class World:
    key: str
    name: str
    unlock_level: int
    sky: tuple[int, int, int]
    skyline: tuple[int, int, int]
    track: tuple[int, int, int]
    accent: tuple[int, int, int]
    hazards: tuple[str, ...]
    atmosphere: str


WORLDS = (
    World("city", "MERIDIAN CITY", 1, (10, 16, 36), (18, 31, 56), (20, 28, 43), (63, 231, 235),
          ("barrier", "gate", "electric_car", "fence"), "neon"),
    World("metro", "UNDERGROUND LOOP", 2, (12, 19, 31), (21, 36, 48), (24, 31, 38), (255, 190, 87),
          ("barrier", "gate", "electric_car"), "subway"),
    World("industrial", "ION WORKS", 3, (25, 17, 29), (47, 28, 42), (35, 29, 40), (255, 94, 120),
          ("barrier", "fence", "electric_car"), "industrial"),
    World("rooftops", "SKYLINE ROOFTOPS", 4, (13, 28, 47), (24, 44, 68), (23, 35, 50), (117, 185, 255),
          ("barrier", "gate", "fence"), "wind"),
    World("night_market", "NIGHT MARKET", 5, (31, 17, 38), (54, 29, 58), (38, 27, 45), (255, 114, 187),
          ("barrier", "gate", "electric_car", "fence"), "market"),
    World("highway", "ION HIGHWAY", 6, (8, 20, 38), (16, 37, 62), (18, 31, 48), (91, 211, 255),
          ("barrier", "electric_car", "fence"), "highway"),
    World("arcade", "DIGITAL ARCADE", 7, (19, 15, 48), (37, 25, 77), (25, 22, 56), (184, 113, 255),
          ("barrier", "gate", "electric_car"), "arcade"),
)


def unlocked_worlds(profile_level: int) -> tuple[World, ...]:
    return tuple(world for world in WORLDS if profile_level >= world.unlock_level)


def active_world(distance: float, profile_level: int, selected: str = "city") -> World:
    available = unlocked_worlds(profile_level) or (WORLDS[0],)
    start = next((index for index, world in enumerate(available) if world.key == selected), 0)
    segment = max(0, int(distance // 5000))
    return available[(start + segment) % len(available)]
