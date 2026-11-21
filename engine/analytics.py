"""Local run telemetry, adaptive difficulty, and evidence-based coaching."""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass, field
import math


@dataclass
class RunTelemetry:
    elapsed: float = 0.0
    distance: float = 0.0
    score: int = 0
    coins: int = 0
    lane_changes: int = 0
    lane_change_threats: int = 0
    lane_change_successes: int = 0
    jumps: int = 0
    slides: int = 0
    jump_successes: int = 0
    slide_successes: int = 0
    dash_activations: int = 0
    dash_clears: int = 0
    near_misses: int = 0
    collisions: dict[str, int] = field(default_factory=dict)
    powerups: dict[str, int] = field(default_factory=dict)
    reaction_samples: list[float] = field(default_factory=list)

    @property
    def successful_avoids(self) -> int:
        return (self.jump_successes + self.slide_successes + self.lane_change_successes
                + self.dash_clears + self.near_misses)

    @property
    def collision_count(self) -> int:
        return sum(self.collisions.values())

    def collision(self, kind: str) -> None:
        self.collisions[kind] = self.collisions.get(kind, 0) + 1

    def powerup(self, kind: str) -> None:
        self.powerups[kind] = self.powerups.get(kind, 0) + 1

    def reaction(self, seconds: float) -> None:
        if math.isfinite(seconds) and seconds >= 0:
            self.reaction_samples.append(seconds)
            del self.reaction_samples[:-64]

    def summary(self) -> dict:
        result = asdict(self)
        result["successful_avoids"] = self.successful_avoids
        result["collision_count"] = self.collision_count
        result["average_reaction"] = (sum(self.reaction_samples) / len(self.reaction_samples)
                                      if self.reaction_samples else None)
        return result


class PlayerAnalytics:
    """Bounded local history and lifetime counters; never records identity data."""

    MAX_RUNS = 100

    def __init__(self, state: object = None) -> None:
        state = state if isinstance(state, dict) else {}
        raw_runs = state.get("runs", [])
        self.runs = [self._normalize_run(item) for item in raw_runs
                     if isinstance(raw_runs, list) and isinstance(item, dict)][-self.MAX_RUNS:] \
            if isinstance(raw_runs, list) else []
        self.totals = {key: self._counter(state.get("totals", {}), key)
                       for key in ("runs", "distance", "coins", "collisions", "dash_clears", "near_misses")}
        self.preferred_lane = self._valid_lane(state.get("preferred_lane", 1))
        self.lane_counts = [self._counter(state.get("lane_counts", []), str(i)) for i in range(3)]

    @staticmethod
    def _counter(container: object, key: str) -> int:
        try:
            value = container.get(key, 0) if isinstance(container, dict) else container[int(key)]
            return max(0, min(2_147_483_647, int(value)))
        except (IndexError, KeyError, TypeError, ValueError, OverflowError):
            return 0

    @staticmethod
    def _valid_lane(value: object) -> int:
        try:
            return max(0, min(2, int(value)))
        except (TypeError, ValueError, OverflowError):
            return 1

    @classmethod
    def _normalize_run(cls, raw: dict) -> dict:
        metrics = ("elapsed", "distance", "score", "coins", "lane_changes",
                   "lane_change_threats", "lane_change_successes", "jumps",
                   "slides", "jump_successes", "slide_successes", "dash_activations",
                   "dash_clears", "near_misses", "collision_count", "successful_avoids",
                   "powerup_count")
        result = {key: cls._counter(raw, key) for key in metrics}
        for field_name in ("collisions", "powerups"):
            field = raw.get(field_name, {})
            result[field_name] = ({str(kind)[:40]: cls._counter(field, str(kind))
                                   for kind in field if isinstance(kind, str)}
                                  if isinstance(field, dict) else {})
        try:
            factor = float(raw.get("difficulty_factor"))
            result["difficulty_factor"] = max(.82, min(1.16, factor)) if math.isfinite(factor) else None
        except (TypeError, ValueError, OverflowError):
            result["difficulty_factor"] = None
        preference = raw.get("difficulty_preference")
        result["difficulty_preference"] = (preference if isinstance(preference, str)
                                            and preference in AdaptiveDifficulty.PREFERENCES else None)
        samples = raw.get("reaction_samples", [])
        if not isinstance(samples, list):
            samples = []
        result["reaction_samples"] = []
        for value in samples[-64:]:
            try:
                number = float(value)
                if math.isfinite(number) and number >= 0:
                    result["reaction_samples"].append(min(number, 60.0))
            except (TypeError, ValueError, OverflowError):
                continue
        average = raw.get("average_reaction")
        try:
            average = float(average)
            result["average_reaction"] = min(60.0, average) if math.isfinite(average) and average >= 0 else None
        except (TypeError, ValueError, OverflowError):
            result["average_reaction"] = None
        consistency = raw.get("consistency")
        try:
            consistency = float(consistency)
            result["consistency"] = max(0.0, min(1.0, consistency)) if math.isfinite(consistency) else None
        except (TypeError, ValueError, OverflowError):
            result["consistency"] = None
        return result

    def record(self, summary: dict, preferred_lane: int) -> None:
        self.runs.append(summary)
        del self.runs[:-self.MAX_RUNS]
        self.totals["runs"] += 1
        self.totals["distance"] += max(0, int(summary.get("distance", 0)))
        self.totals["coins"] += max(0, int(summary.get("coins", 0)))
        self.totals["collisions"] += max(0, int(summary.get("collision_count", 0)))
        self.totals["dash_clears"] += max(0, int(summary.get("dash_clears", 0)))
        self.totals["near_misses"] += max(0, int(summary.get("near_misses", 0)))
        lane = self._valid_lane(preferred_lane)
        self.lane_counts[lane] += 1
        self.preferred_lane = max(range(3), key=lambda item: (self.lane_counts[item], -item))

    def to_data(self) -> dict:
        return {"runs": self.runs, "totals": self.totals,
                "preferred_lane": self.preferred_lane, "lane_counts": self.lane_counts}

    def performance_consistency(self) -> float | None:
        """Return bounded consistency from the recent avoid/collision rates."""
        rates = []
        for run in self.runs[-5:]:
            avoids = max(0, int(run.get("successful_avoids", 0)))
            collisions = max(0, int(run.get("collision_count", 0)))
            if avoids + collisions:
                rates.append(avoids / (avoids + collisions))
        if len(rates) < 3:
            return None
        mean = sum(rates) / len(rates)
        variance = sum((rate-mean)**2 for rate in rates) / len(rates)
        return max(0.0, min(1.0, 1.0 - math.sqrt(variance)))

    def coach(self) -> str:
        if len(self.runs) < 3:
            return "Complete a few more runs to build a useful performance trend."
        recent = self.runs[-5:]
        jumps = sum(int(run.get("jumps", 0)) for run in recent)
        jump_success = sum(int(run.get("jump_successes", 0)) for run in recent)
        slides = sum(int(run.get("slides", 0)) for run in recent)
        slide_success = sum(int(run.get("slide_successes", 0)) for run in recent)
        collisions = Counter()
        for run in recent:
            if isinstance(run.get("collisions"), dict):
                collisions.update(run["collisions"])
        avoidable_actions = [(jump_success / jumps if jumps else 1.0, "jump") ,
                             (slide_success / slides if slides else 1.0, "slide")]
        weakest_rate, action = min(avoidable_actions)
        if collisions and weakest_rate < .65:
            return f"Your recent {action} success is {weakest_rate:.0%}; practise timing that move before the next barrier."
        if collisions:
            kind = collisions.most_common(1)[0][0]
            return f"Most recent collisions involved {kind.replace('_', ' ')}. Keep an escape lane open before it reaches you."
        return "Your last few runs were collision-free. Try a longer distance or a higher difficulty."


class AdaptiveDifficulty:
    """Gradual bounded multiplier driven by the current run's observed decisions."""

    PREFERENCES = {"relaxed": .90, "balanced": 1.0, "challenge": 1.08}

    def __init__(self, preference: str = "balanced", factor: float | None = None) -> None:
        self.preference = preference if preference in self.PREFERENCES else "balanced"
        base = self.PREFERENCES[self.preference]
        try:
            requested = float(factor) if factor is not None else base
            self.factor = max(.82, min(1.16, requested))
        except (TypeError, ValueError, OverflowError):
            self.factor = base
        self.decisions = 0
        self.successes = 0

    def set_preference(self, preference: str) -> None:
        if preference in self.PREFERENCES:
            self.preference = preference
            self.factor = max(.82, min(1.16, self.factor * .85 + self.PREFERENCES[preference] * .15))

    def observe_run(self, summary: dict) -> float:
        """Fold measured run success, survival, and reaction data into difficulty."""
        avoids = max(0, int(summary.get("successful_avoids", 0)))
        collisions = max(0, int(summary.get("collision_count", 0)))
        attempts = avoids + collisions
        if attempts == 0:
            return self.factor
        success_rate = avoids / attempts
        # Incorporate the player's actual movement choices when that data
        # exists, while keeping sparse or optional actions from skewing pace.
        action_rates = []
        for attempts_key, successes_key in (("jumps", "jump_successes"),
                                             ("slides", "slide_successes"),
                                             ("lane_change_threats", "lane_change_successes")):
            action_count = max(0, int(summary.get(attempts_key, 0)))
            if action_count:
                action_rates.append(max(0, min(action_count, int(summary.get(successes_key, 0))))
                                    / action_count)
        if action_rates:
            success_rate = success_rate * .65 + (sum(action_rates) / len(action_rates)) * .35
        dash_uses = max(0, int(summary.get("dash_activations", 0)))
        dash_clears = max(0, int(summary.get("dash_clears", 0)))
        if dash_uses:
            success_rate = success_rate * .9 + min(1.0, dash_clears / dash_uses) * .1
        # Power-up use is tracked as a context signal, not treated as skill.
        # A small experience bonus avoids ramping difficulty for players who
        # have barely encountered the run systems yet.
        powerup_count = max(0, int(summary.get("powerup_count", 0)))
        if powerup_count and attempts < 3:
            success_rate = min(1.0, success_rate + .015)
        reaction = summary.get("average_reaction")
        reaction_bonus = 0.0
        if isinstance(reaction, (int, float)) and math.isfinite(reaction):
            reaction_bonus = max(-.025, min(.025, (.8 - reaction) * .04))
        consistency = summary.get("consistency")
        consistency_adjustment = 0.0
        if isinstance(consistency, (int, float)) and math.isfinite(consistency):
            consistency_adjustment = (max(0.0, min(1.0, consistency)) - .5) * .025
        target = self.PREFERENCES[self.preference] * (
            .88 + .22 * success_rate + reaction_bonus + consistency_adjustment)
        if float(summary.get("elapsed", 0)) < 20 and collisions >= 2:
            target = min(target, self.PREFERENCES[self.preference] * .92)
        target = max(.82, min(1.16, target))
        self.factor = max(.82, min(1.16, self.factor + (target - self.factor) * .12))
        return self.factor

    def observe(self, success: bool, reaction_seconds: float | None = None) -> float:
        self.decisions += 1
        self.successes += int(bool(success))
        rate = self.successes / self.decisions
        reaction_bonus = 0.0
        if reaction_seconds is not None and math.isfinite(reaction_seconds):
            reaction_bonus = max(-.025, min(.025, (.8 - reaction_seconds) * .04))
        target = self.PREFERENCES[self.preference] * (.88 + .24 * rate + reaction_bonus)
        target = max(.82, min(1.16, target))
        # A small EMA update keeps each result gradual and predictable.
        self.factor = max(.82, min(1.16, self.factor + (target - self.factor) * .06))
        return self.factor
