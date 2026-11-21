"""Pure difficulty curves kept separate from the frame loop for tuning/tests."""


class DifficultyCurve:
    CALM_SPEED_CAP = 270.0
    STANDARD_SPEED_CAP = 365.0
    CALM_SPAWN_FLOOR = 1.05
    STANDARD_SPAWN_FLOOR = 0.73

    @classmethod
    def speed(cls, elapsed: float, calm: bool, overdrive: bool = False,
              adaptive_factor: float = 1.0) -> float:
        elapsed = max(0.0, elapsed)
        adaptive_factor = max(.82, min(1.16, adaptive_factor))
        if calm:
            return min(cls.CALM_SPEED_CAP, (150 + elapsed * 1.25 + (24 if overdrive else 0)) * adaptive_factor)
        return min(cls.STANDARD_SPEED_CAP, (190 + elapsed * 2.5 + (42 if overdrive else 0)) * adaptive_factor)

    @classmethod
    def spawn_interval(cls, elapsed: float, calm: bool, adaptive_factor: float = 1.0) -> float:
        elapsed = max(0.0, elapsed)
        adaptive_factor = max(.82, min(1.16, adaptive_factor))
        if calm:
            return max(cls.CALM_SPAWN_FLOOR, (1.48 - elapsed * .002) / adaptive_factor)
        return max(cls.STANDARD_SPAWN_FLOOR, (1.20 - elapsed * .0035) / adaptive_factor)
