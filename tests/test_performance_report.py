"""Repeatable offscreen CPU-render timing (not a hardware/GPU FPS claim)."""

import os
import time

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

import engine.game as game_module
from database.save_manager import SaveManager
from engine.game import NeonRunner


class SilentAudio:
    muted = False

    def set_music_volume(self, _value): pass
    def set_sfx_volume(self, _value): pass
    def set_boost(self, _active): pass
    def play(self, _name): pass
    def toggle_mute(self): self.muted = not self.muted


def test_report_offscreen_gameplay_frame_time(tmp_path, monkeypatch):
    pygame.init()
    pygame.display.set_mode((960, 540))
    save = SaveManager(tmp_path / "benchmark.sqlite3")
    monkeypatch.setattr(game_module, "SaveManager", lambda: save)
    monkeypatch.setattr(game_module, "AudioBus", SilentAudio)
    runner = NeonRunner()
    runner.begin_run()
    for _ in range(3):
        runner.spawn_pattern()

    samples = []
    try:
        for _ in range(240):
            start = time.perf_counter()
            runner.update(1 / 60)
            runner.draw()
            samples.append(time.perf_counter() - start)
        ordered = sorted(samples)
        mean_ms = sum(samples) / len(samples) * 1000
        p95_ms = ordered[int(len(ordered) * .95) - 1] * 1000
        print(f"offscreen software draw+update: mean={mean_ms:.2f}ms, p95={p95_ms:.2f}ms; 240 frames")
        assert mean_ms > 0 and p95_ms > 0
    finally:
        save.close()
        pygame.quit()
