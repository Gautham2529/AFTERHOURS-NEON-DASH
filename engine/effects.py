"""Bounded lightweight gameplay particles that respect reduced-motion mode."""

import math
import random

import pygame


class ParticlePool:
    CAPACITY = 64

    def __init__(self, seed: int | None = None) -> None:
        self.rng = random.Random(seed)
        self.particles: list[dict] = []

    def emit(self, x: float, y: float, color: tuple[int, int, int], reduced_motion: bool = False) -> None:
        if reduced_motion:
            return
        for _ in range(6):
            if len(self.particles) >= self.CAPACITY:
                break
            self.particles.append({"x": float(x), "y": float(y),
                                   "vx": self.rng.uniform(-34, 34),
                                   "vy": self.rng.uniform(-72, -18),
                                   "life": self.rng.uniform(.22, .42),
                                   "color": color})

    def emit_burst(self, x: float, y: float, color: tuple[int, int, int],
                   reduced_motion: bool = False) -> None:
        if reduced_motion:
            return
        for _ in range(14):
            if len(self.particles) >= self.CAPACITY:
                break
            angle = self.rng.uniform(0, 6.283185307179586)
            speed = self.rng.uniform(35, 105)
            self.particles.append({"x": float(x), "y": float(y),
                                  "vx": math.cos(angle) * speed,
                                  "vy": math.sin(angle) * speed,
                                  "life": self.rng.uniform(.28, .55),
                                  "color": color})

    def emit_trail(self, x: float, y: float, color: tuple[int, int, int],
                   reduced_motion: bool = False) -> None:
        if reduced_motion:
            return
        for _ in range(2):
            if len(self.particles) >= self.CAPACITY:
                break
            self.particles.append({"x": float(x) + self.rng.uniform(-7, 7),
                                   "y": float(y) + self.rng.uniform(-4, 4),
                                   "vx": self.rng.uniform(-12, 12),
                                   "vy": self.rng.uniform(24, 58),
                                   "life": self.rng.uniform(.12, .24),
                                   "color": color})

    def update(self, dt: float) -> None:
        retained = []
        for particle in self.particles:
            particle["life"] -= dt
            particle["x"] += particle["vx"] * dt
            particle["y"] += particle["vy"] * dt
            particle["vy"] += 110 * dt
            if particle["life"] > 0:
                retained.append(particle)
        self.particles = retained

    def clear(self) -> None:
        self.particles.clear()

    def draw(self, target: pygame.Surface) -> None:
        for particle in self.particles:
            radius = max(1, int(3 * particle["life"] / .42))
            center = (int(particle["x"]), int(particle["y"]))
            color = particle["color"]
            if radius > 1:
                halo = tuple(channel // 3 for channel in color)
                pygame.draw.circle(target, halo, center, radius + 2)
            pygame.draw.circle(target, color, center, radius)
