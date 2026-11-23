"""Fair, constrained one-row patterns for the three-lane track."""

from __future__ import annotations

import random


class PatternGenerator:
    """Generate a single hazard lane or one collectible trail per pattern.

    Hazard patterns deliberately leave two lanes open. A short history also
    prevents the same hazard lane from being selected three times in a row.
    The supplied random generator makes patterns reproducible in tests.
    """

    HAZARDS = ("barrier", "gate", "electric_car", "fence")
    PICKUPS = ("coin", "battery", "shield", "magnet", "score_boost", "overdrive", "coin_bonus")
    HAZARD_KINDS = frozenset(HAZARDS)
    DEFAULT_REACTION_WINDOW = .22

    def __init__(self, rng: random.Random | None = None) -> None:
        self.rng = rng or random.Random()
        self.history: list[tuple[int, str]] = []

    def generate(self, battery_level: int = 0, intensity: float = 1.0,
                 hazard_pool: tuple[str, ...] | None = None) -> list[dict]:
        """Generate a hazard or pickup pattern and update recent-pattern history."""
        hazards = tuple(item for item in (hazard_pool or self.HAZARDS) if item in self.HAZARDS)
        if not hazards:
            hazards = self.HAZARDS
        lane = self.rng.randrange(3)
        if len(self.history) >= 2 and self.history[-1][0] == self.history[-2][0] == lane:
            lane = self.rng.choice([candidate for candidate in range(3) if candidate != lane])

        hazard_chance = max(.42, min(.68, .60 + (intensity - 1.0) * .45))
        if self.rng.random() < hazard_chance:
            kind = self.rng.choice(hazards)
            if self.history and kind == self.history[-1][1]:
                alternatives = [item for item in hazards if item != kind]
                if alternatives:
                    kind = self.rng.choice(alternatives)
            pattern = [{"kind": kind, "lane": lane, "y": 145.0}]
            if self.rng.random() < 0.58:
                alt = (lane + self.rng.choice((1, 2))) % 3
                pattern.extend({"kind": "coin", "lane": alt, "y": 175.0 - i * 34}
                               for i in range(4))
        else:
            battery_level = max(0, min(5, int(battery_level)))
            weights = (58 - battery_level * 2, 13 + battery_level * 2, 6, 7, 7, 5, 4)
            kind = self.rng.choices(self.PICKUPS, weights)[0]
            count = 5 if kind == "coin" else 1
            pattern = [{"kind": kind, "lane": lane, "y": 145.0 - i * 36}
                       for i in range(count)]

        self.history.append((lane, kind))
        del self.history[:-4]
        return pattern

    @classmethod
    def has_reachable_route(cls, patterns: list[dict] | tuple[dict, ...], speed: float,
                            player_lane: int, reaction_window: float = DEFAULT_REACTION_WINDOW,
                            lane_change_seconds: float = .18) -> bool:
        """Check a sequence of hazard crossing times for a reaction-feasible lane path.

        This conservative validator treats every hazard type as lane-blocking;
        it does not require the player to own a shield, dash, jump, or slide.
        Hazards arriving within 80 ms are evaluated as one combined row.
        """
        safe_speed = max(1.0, float(speed))
        window = max(0.0, float(reaction_window))
        switch_time = max(0.0, float(lane_change_seconds))
        events = cls._hazard_crossings(patterns, safe_speed)
        if events is None:
            return False
        groups = cls._group_crossings(events)
        return cls._route_exists(groups, player_lane, window, switch_time)

    @classmethod
    def _hazard_crossings(
        cls, patterns: list[dict] | tuple[dict, ...], safe_speed: float,
    ) -> list[tuple[float, int]] | None:
        """Convert valid hazard entities into crossing-time events."""
        events: list[tuple[float, int]] = []
        for item in patterns:
            if not isinstance(item, dict) or item.get("kind") not in cls.HAZARD_KINDS:
                continue
            try:
                lane = int(item.get("lane", -1))
                y = float(item.get("y", 0))
            except (TypeError, ValueError, OverflowError):
                return None
            if lane not in (0, 1, 2) or y >= 432:
                continue
            crossing_time = max(0.0, (432.0 - y) / safe_speed)
            events.append((crossing_time, lane))
        return events

    @staticmethod
    def _group_crossings(events: list[tuple[float, int]]) -> list[tuple[float, set[int]]]:
        """Merge hazard events arriving within 80 ms into the same row."""
        groups: list[tuple[float, set[int]]] = []
        for crossing_time, lane in sorted(events):
            if groups and crossing_time - groups[-1][0] <= .08:
                groups[-1][1].add(lane)
            else:
                groups.append((crossing_time, {lane}))
        return groups

    @staticmethod
    def _route_exists(groups: list[tuple[float, set[int]]], player_lane: int,
                      window: float, switch_time: float) -> bool:
        """Check whether any collision-free lane remains reachable per hazard row."""
        if not groups:
            return True
        reachable = {max(0, min(2, int(player_lane)))}
        previous_time = 0.0
        for crossing_time, blocked in groups:
            reaction = crossing_time - previous_time
            next_lanes = {
                lane for lane in range(3) if lane not in blocked
                and any((lane == old_lane or max(window, abs(lane - old_lane) * switch_time)
                         <= reaction + 1e-9) for old_lane in reachable)
            }
            if not next_lanes:
                return False
            reachable = next_lanes
            previous_time = crossing_time
        return True
