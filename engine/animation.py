"""Physics-independent character animation state selection."""

from __future__ import annotations


class CharacterAnimationController:
    """Prioritized one-shot reactions layered over locomotion animation states."""

    DURATIONS = {
        "jump_prep": .08, "landing": .16, "hit": .28, "shield": .38,
        "powerup": .30, "defeat": .9, "victory": .55, "milestone": .45,
    }
    PRIORITIES = {"jump_prep": 1, "landing": 1, "powerup": 2, "milestone": 2,
                  "shield": 3, "hit": 4, "victory": 4, "defeat": 5}

    def __init__(self) -> None:
        self.state = "run"
        self.timer = 0.0
        self.priority = 0
        self.revision = 0

    def trigger(self, state: str) -> bool:
        """Start a recognized reaction unless a higher-priority one is active."""
        duration = self.DURATIONS.get(state)
        if duration is None or self.PRIORITIES[state] < self.priority:
            return False
        self.state = state
        self.timer = duration
        self.priority = self.PRIORITIES[state]
        self.revision += 1
        return True

    def update(self, dt: float, locomotion: str) -> str:
        """Advance the active reaction and return its current animation state."""
        if locomotion not in {"idle", "run", "jump", "fall", "slide", "dash"}:
            locomotion = "run"
        if self.timer > 0:
            self.timer = max(0.0, self.timer - max(0.0, dt))
            if self.timer > 0:
                return self.state
        self.priority = 0
        if self.state != locomotion:
            self.state = locomotion
            self.revision += 1
        return self.state
