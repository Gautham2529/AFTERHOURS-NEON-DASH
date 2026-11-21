import random
import time
import tkinter as tk


WIDTH = 900
HEIGHT = 600
HORIZON = 170
GROUND = 505
LANES = (300, 450, 600)
RUN_TIME = 90


class MetroDash:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Metro Dash")
        self.root.resizable(False, False)
        self.canvas = tk.Canvas(root, width=WIDTH, height=HEIGHT,
                                bg="#9ebdc5", highlightthickness=0)
        self.canvas.pack()

        self.root.bind("<Left>", lambda _event: self.move_lane(-1))
        self.root.bind("<Right>", lambda _event: self.move_lane(1))
        self.root.bind("<a>", lambda _event: self.move_lane(-1))
        self.root.bind("<d>", lambda _event: self.move_lane(1))
        self.root.bind("<Up>", lambda _event: self.jump())
        self.root.bind("<w>", lambda _event: self.jump())
        self.root.bind("<Down>", lambda _event: self.slide())
        self.root.bind("<s>", lambda _event: self.slide())
        self.root.bind("<space>", lambda _event: self.toggle_pause())
        self.root.bind("<r>", lambda _event: self.start_game())
        self.start_game()

    def start_game(self) -> None:
        self.lane = 1
        self.player_x = LANES[1]
        self.jump_height = 0.0
        self.jump_velocity = 0.0
        self.slide_timer = 0.0
        self.score = 0
        self.coins = 0
        self.lives = 3
        self.entities: list[dict] = []
        self.spawn_timer = 0.8
        self.started = time.monotonic()
        self.last_tick = self.started
        self.running = True
        self.paused = False
        self.hit_timer = 0.0
        self.draw()
        self.root.after(16, self.loop)

    def move_lane(self, offset: int) -> None:
        if self.running and not self.paused:
            self.lane = max(0, min(2, self.lane + offset))

    def jump(self) -> None:
        if self.running and not self.paused and self.jump_height == 0:
            self.jump_velocity = 620

    def slide(self) -> None:
        if self.running and not self.paused and self.jump_height == 0:
            self.slide_timer = 0.6

    def toggle_pause(self) -> None:
        if self.running:
            self.paused = not self.paused
            self.draw()

    def loop(self) -> None:
        if not self.running:
            return
        now = time.monotonic()
        dt = min(now - self.last_tick, 0.05)
        self.last_tick = now
        elapsed = now - self.started

        if not self.paused:
            if elapsed >= RUN_TIME:
                self.running = False
            else:
                self.update(dt)
        self.draw()
        self.root.after(16, self.loop)

    def update(self, dt: float) -> None:
        elapsed = time.monotonic() - self.started
        speed = 330 + elapsed * 2.2

        target_x = LANES[self.lane]
        self.player_x += (target_x - self.player_x) * min(1.0, dt * 12)

        if self.jump_velocity:
            self.jump_height += self.jump_velocity * dt
            self.jump_velocity -= 1250 * dt
            if self.jump_height <= 0:
                self.jump_height = 0
                self.jump_velocity = 0
        self.slide_timer = max(0.0, self.slide_timer - dt)
        self.hit_timer = max(0.0, self.hit_timer - dt)

        self.spawn_timer -= dt
        if self.spawn_timer <= 0:
            self.spawn_entity()
            self.spawn_timer = random.uniform(0.62, 0.95)

        for entity in self.entities:
            entity["distance"] += speed * dt

        retained = []
        for entity in self.entities:
            distance = entity["distance"]
            if distance > 720:
                continue

            if 610 < distance < 690 and entity["lane"] == self.lane:
                kind = entity["kind"]
                if kind == "coin":
                    self.coins += 1
                    self.score += 25
                    continue
                if kind == "barrier" and self.jump_height > 55:
                    pass
                elif kind == "sign" and self.slide_timer > 0:
                    pass
                else:
                    if self.hit_timer == 0:
                        self.lives -= 1
                        self.hit_timer = 1.2
                        self.score = max(0, self.score - 50)
                        if self.lives <= 0:
                            self.running = False
                    continue
            retained.append(entity)
        self.entities = retained

    def spawn_entity(self) -> None:
        lane = random.randrange(3)
        roll = random.random()
        if roll < 0.34:
            count = 3 if random.random() < 0.25 else 1
            for index in range(count):
                self.entities.append({"kind": "coin", "lane": lane,
                                      "distance": -index * 48})
        else:
            kind = "train" if roll > 0.78 else "barrier" if roll > 0.58 else "sign"
            self.entities.append({"kind": kind, "lane": lane, "distance": 0})

    def project(self, lane: int, distance: float) -> tuple[float, float, float]:
        progress = max(0.0, min(1.0, distance / 710))
        eased = progress * progress
        x = WIDTH // 2 + (LANES[lane] - WIDTH // 2) * (0.18 + 0.82 * eased)
        y = HORIZON + (GROUND - HORIZON) * eased
        scale = 0.28 + 0.95 * eased
        return x, y, scale

    def draw(self) -> None:
        self.canvas.delete("all")
        self.draw_world()

        for entity in sorted(self.entities, key=lambda item: item["distance"]):
            x, y, scale = self.project(entity["lane"], entity["distance"])
            if entity["kind"] == "coin":
                self.draw_coin(x, y, scale)
            elif entity["kind"] == "barrier":
                self.draw_barrier(x, y, scale)
            elif entity["kind"] == "sign":
                self.draw_sign(x, y, scale)
            else:
                self.draw_train(x, y, scale)

        self.draw_player()

        elapsed = max(0, int(time.monotonic() - self.started))
        remaining = max(0, RUN_TIME - elapsed)
        self.draw_hud(remaining)

        if self.paused:
            self.draw_overlay("PAUSED", "Press Space to continue")
        elif not self.running:
            title = "RUN COMPLETE" if remaining == 0 else "GAME OVER"
            self.draw_overlay(title,
                              f"Score {self.score}  |  Coins {self.coins}  |  R to run again")

    def draw_world(self) -> None:
        self.canvas.create_rectangle(
            0, 0, WIDTH, HORIZON + 20, fill="#91bac6", outline="")
        self.canvas.create_rectangle(
            0, HORIZON + 20, WIDTH, GROUND + 70, fill="#343b3d", outline="")
        self.canvas.create_oval(720, 40, 805, 125, fill="#f1d78f", outline="")

        for index in range(12):
            base = 10 + index * 82
            height = 35 + (index * 29) % 75
            color = "#59696b" if index % 2 == 0 else "#667779"
            self.canvas.create_rectangle(base, HORIZON - height,
                                         base + 60, HORIZON + 24,
                                         fill=color, outline="#3d4a4b")
            for row in range(2):
                for column in range(3):
                    self.canvas.create_rectangle(base + 9 + column * 16,
                                                 HORIZON - height + 10 + row * 20,
                                                 base + 17 + column * 16,
                                                 HORIZON - height + 19 + row * 20,
                                                 fill="#bad1d1", outline="")

        for lane in LANES:
            self.canvas.create_line(WIDTH // 2, HORIZON, lane, GROUND,
                                    fill="#ccd4d1", width=4)
        for index in range(1, 13):
            y = HORIZON + (GROUND - HORIZON) * (index / 12) ** 2
            scale = 0.18 + index / 12
            for lane in LANES:
                x = WIDTH // 2 + (lane - WIDTH // 2) * scale
                self.canvas.create_oval(x - 3, y - 2, x + 3, y + 2,
                                        fill="#d8b84d", outline="")

        self.canvas.create_polygon(0, GROUND, 228, GROUND, 370, HEIGHT,
                                   0, HEIGHT, fill="#202729", outline="")
        self.canvas.create_polygon(WIDTH, GROUND, 672, GROUND, 530, HEIGHT,
                                   WIDTH, HEIGHT, fill="#202729", outline="")

    def draw_coin(self, x: float, y: float, scale: float) -> None:
        radius = max(7, int(21 * scale))
        cy = y - 58 * scale
        self.canvas.create_oval(x - radius, cy - radius, x + radius, cy + radius,
                                fill="#efc64d", outline="#fff2a8", width=2)
        self.canvas.create_text(x, cy, text="$", fill="#98701f",
                                font=("Arial", max(8, int(17 * scale)), "bold"))

    def draw_barrier(self, x: float, y: float, scale: float) -> None:
        width = int(72 * scale)
        height = int(42 * scale)
        self.canvas.create_rectangle(x - width, y - height, x + width, y,
                                     fill="#d7d8d2", outline="#66706f", width=3)
        for offset in range(-width, width, max(12, int(21 * scale))):
            self.canvas.create_polygon(x + offset, y - height,
                                       x + offset + 13, y - height,
                                       x + offset - 4, y,
                                       x + offset - 18, y,
                                       fill="#bd4b45", outline="")

    def draw_sign(self, x: float, y: float, scale: float) -> None:
        width = int(78 * scale)
        height = int(52 * scale)
        cy = y - int(80 * scale)
        self.canvas.create_rectangle(x - width, cy - height, x + width, cy,
                                     fill="#e3b748", outline="#514830", width=3)
        self.canvas.create_text(x, cy - height // 2, text="LOW",
                                fill="#354247", font=("Arial", max(8, int(19 * scale)), "bold"))

    def draw_train(self, x: float, y: float, scale: float) -> None:
        width = int(92 * scale)
        height = int(175 * scale)
        top = y - height
        self.canvas.create_rectangle(x - width, top, x + width, y,
                                     fill="#b6bbb6", outline="#4e5758", width=4)
        self.canvas.create_rectangle(x - int(width * 0.72), top + int(24 * scale),
                                     x + int(width * 0.72), top +
                                     int(94 * scale),
                                     fill="#42636b", outline="#dce2df", width=3)

    def draw_player(self) -> None:
        x = int(self.player_x)
        base_y = int(GROUND - self.jump_height)
        shirt = "#f1a65a" if self.hit_timer > 0 else "#df4b38"

        self.canvas.create_oval(x - 28, base_y - 8, x + 28, base_y + 18,
                                fill="#1b2021", outline="")
        if self.slide_timer > 0:
            self.canvas.create_oval(x - 24, base_y - 46, x + 24, base_y,
                                    fill="#c88961", outline="#56382c", width=2)
            self.canvas.create_rectangle(x - 40, base_y - 34, x + 38,
                                         base_y - 4, fill=shirt,
                                         outline="#702d26", width=3)
        else:
            self.canvas.create_oval(x - 20, base_y - 98, x + 20, base_y - 58,
                                    fill="#c88961", outline="#56382c", width=2)
            self.canvas.create_rectangle(x - 30, base_y - 62, x + 30,
                                         base_y - 18, fill=shirt,
                                         outline="#702d26", width=3)
            self.canvas.create_rectangle(x - 24, base_y - 18, x - 5, base_y,
                                         fill="#2e3d48", outline="")
            self.canvas.create_rectangle(x + 5, base_y - 18, x + 24, base_y,
                                         fill="#2e3d48", outline="")

    def draw_hud(self, remaining: int) -> None:
        self.canvas.create_rectangle(18, 18, 882, 82, fill="#172023",
                                     outline="#89a2a4", width=2)
        self.canvas.create_text(42, 50, anchor="w", text="METRO DASH",
                                fill="#f2eee2", font=("Arial", 20, "bold"))
        self.canvas.create_text(420, 50, text=f"SCORE  {self.score:05}",
                                fill="#f2eee2", font=("Consolas", 18, "bold"))
        self.canvas.create_text(650, 50, text=f"COINS  {self.coins}",
                                fill="#f3c64d", font=("Consolas", 18, "bold"))
        time_color = "#86dfbd" if remaining > 20 else "#f06d62"
        self.canvas.create_text(838, 50, anchor="e", text=f"{remaining:02}s",
                                fill=time_color, font=("Consolas", 22, "bold"))
        for index in range(3):
            x = 786 + index * 24
            color = "#df4b38" if index < self.lives else "#4b5556"
            self.canvas.create_oval(x - 8, 86, x + 8, 102,
                                    fill=color, outline="")

    def draw_overlay(self, title: str, subtitle: str) -> None:
        self.canvas.create_rectangle(170, 240, 730, 405, fill="#172023",
                                     outline="#91b0ad", width=3)
        self.canvas.create_text(WIDTH // 2, 292, text=title,
                                fill="#f2eee2", font=("Arial", 38, "bold"))
        self.canvas.create_text(WIDTH // 2, 344, text=subtitle,
                                fill="#b9c9c6", font=("Consolas", 16))


if __name__ == "__main__":
    window = tk.Tk()
    MetroDash(window)
    window.mainloop()
