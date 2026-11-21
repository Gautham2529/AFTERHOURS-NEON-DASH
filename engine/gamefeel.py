"""Small bounded systems for rewarding clean streaks and impact feedback."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar


@dataclass
class ComboTracker:
    """Consecutive clean-play chain with a short decay window and capped bonus."""

    WINDOW: ClassVar[float] = 2.25
    MAX_COUNT: ClassVar[int] = 12
    MAX_BONUS_RATE: ClassVar[float] = .75
    count: int = 0
    time_left: float = 0.0
    best: int = 0

    @property
    def active(self) -> bool:
        return self.count > 0 and self.time_left > 0

    def trigger(self, base_points: int) -> int:
        self.count = min(self.MAX_COUNT, self.count + 1) if self.active else 1
        self.time_left = self.WINDOW
        self.best = max(self.best, self.count)
        rate = min(self.MAX_BONUS_RATE, max(0, self.count - 1) * .12)
        return max(0, int(max(0, base_points) * rate))

    def update(self, dt: float) -> None:
        self.time_left = max(0.0, self.time_left - max(0.0, dt))
        if self.time_left == 0:
            self.count = 0

    def break_chain(self) -> None:
        self.count = 0
        self.time_left = 0.0

    def reset(self) -> None:
        self.break_chain()
        self.best = 0
