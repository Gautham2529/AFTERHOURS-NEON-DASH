"""Small fixed-rate, non-interactive run ghosts for PB and previous-run replay."""

from __future__ import annotations

import math
from bisect import bisect_right


class GhostReplay:
    SAMPLE_RATE = 20
    INTERVAL = 1 / SAMPLE_RATE
    MAX_SAMPLES = 1800  # 90 seconds at 20 Hz.
    MAX_ARCHIVE_RUNS = 5

    def __init__(self, data: object = None) -> None:
        self.samples: list[list[float | int | str]] = []
        self.next_sample = 0.0
        if isinstance(data, list):
            for row in data[-self.MAX_SAMPLES:]:
                if not isinstance(row, (list, tuple)) or len(row) != 6:
                    continue
                try:
                    t, lane, pose, jump, slide, dash = row
                    if not all(math.isfinite(float(v)) for v in (t, lane, jump, slide)):
                        continue
                    self.samples.append([max(0.0, float(t)), max(0.0, min(2.0, float(lane))),
                                         str(pose) if pose in ("run", "jump", "slide", "dash") else "run",
                                         max(0.0, float(jump)), max(0.0, float(slide)), int(bool(dash))])
                except (TypeError, ValueError, OverflowError):
                    continue
            if self.samples:
                self.samples.sort(key=lambda row: row[0])
                self.samples = self.samples[-self.MAX_SAMPLES:]
                self.next_sample = self.samples[-1][0] + self.INTERVAL

    def record(self, elapsed: float, lane: float, pose: str,
               jump_time: float = 0.0, slide_time: float = 0.0, dash: bool = False) -> None:
        try:
            elapsed, lane, jump_time, slide_time = map(float, (elapsed, lane, jump_time, slide_time))
        except (TypeError, ValueError, OverflowError):
            return
        if not all(math.isfinite(value) for value in (elapsed, lane, jump_time, slide_time)):
            return
        if len(self.samples) >= self.MAX_SAMPLES or elapsed + 1e-8 < self.next_sample:
            return
        pose = pose if pose in ("run", "jump", "slide", "dash") else "run"
        self.samples.append([round(max(0.0, elapsed), 3), max(0.0, min(2.0, lane)), pose,
                             max(0.0, jump_time), max(0.0, slide_time), int(dash)])
        self.next_sample += self.INTERVAL

    def at(self, elapsed: float) -> dict | None:
        if not self.samples or elapsed < self.samples[0][0]:
            return None
        if elapsed > self.samples[-1][0] + self.INTERVAL:
            return None
        index = max(0, min(len(self.samples)-1,
                           bisect_right([row[0] for row in self.samples], elapsed) - 1))
        first = self.samples[index]
        second = self.samples[min(index + 1, len(self.samples) - 1)]
        fraction = max(0.0, min(1.0, (elapsed - first[0]) / self.INTERVAL))
        return {"time": first[0], "lane": first[1] + (second[1] - first[1]) * fraction,
                "pose": first[2], "jump": first[3], "slide": first[4], "dash": bool(first[5])}

    def to_data(self) -> list[list[float | int | str]]:
        return [list(row) for row in self.samples[-self.MAX_SAMPLES:]]
