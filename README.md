# AFTERHOURS: NEON DASH

An original three-lane arcade runner set above the Meridian Loop. Dodge ion pylons, laser gates, electric fences, and runaway pulse cars; collect tokens and boosters; and build a high score through increasingly fast run levels.

## Run

```powershell
py -m pip install -r requirements.txt
py main.py
```

## Controls

- `Left` / `A`, `Right` / `D`: switch lanes
- `Up` / `W` / `Space`: jump over ion pylons
- `Down` / `S`: slide under laser gates
- `E`: activate a full dash charge
- `P` / `Esc`: pause; use `U` for upgrades or `C` for runners
- `Enter` / `R`: restart after a run
- `M`: mute or restore sound
- `F11`: toggle fullscreen and windowed display
- Touch screens: swipe left/right to change lanes; swipe up to jump and down to slide. Enable large tap controls from **Comfort & Controls**.

Tokens score points and become upgrade points after the run. Batteries charge the dash. Shields absorb a crash, magnets pull in nearby tokens, score boosts double score gains, and overdrive increases speed and distance. An orange token doubler briefly makes each collected token count twice. The first run starts with a short tutorial. The title screen also has an upgrade garage and runner selection.

## Progression

Spend upgrade points on magnet reach and duration, dash charge and duration, shield capacity, token value, and energy-cell strength. Unlock and select four original runner avatars with small different abilities. Run levels increase with score; profile levels, best score, best token count, upgrades, selected environment, and unlocked runners persist locally in SQLite.

Music and sound effects are synthesized by the game at startup; no downloaded audio assets are required. Booster states layer in a faster soundtrack, and pickups have distinct tones.

Worlds add distinct neon-city, underground, industrial, rooftop, market, highway, and arcade scenery with animated parallax, atmosphere, and transition lighting. The runner is procedurally articulated, while dash trails, pickup bursts, glowing track lights, atmospheric haze, and subtle camera movement respond to the selected reduced-motion settings.

## Comfort

The title screen's **Comfort & Controls** panel saves reduced-motion, reduced-flashing, calm-pace, music, effects, blink-reminder, touch-button, swipe sensitivity, adaptive-pace, and best/previous/saved-run/off ghost preferences. When saved-run mode is active, use left/right on the selected row to choose among the latest five replay tracks. The default run uses a gentler speed curve and wider obstacle spacing. Coin dings are quieter and rapidly repeated coin sounds are rate-limited. Blink reminders are brief and do not pause play.

**Missions & Records** opens behavior-selected one-run missions, two adaptive career contracts that accumulate across runs, offline daily and weekly challenges, lifetime achievements, run statistics, runner profile, world selection, and challenge history. Mission, career-contract, daily, weekly, and achievement rewards are one-time claims stored with the profile; daily and weekly history also prevents duplicate claims if the system date moves backward. Pattern generation leaves two lanes open for each single-lane hazard, checks live hazard crossing times against the reaction window, and reduces repeated lane streaks. Local telemetry records recent runs and supports coarse post-run coaching. Personal-best, previous-run, and selected saved-run ghosts are non-colliding guides. Profile levels unlock seven palette, scenery, hazard, and music variants that rotate during long runs.

## Checks

Run `python -m pytest -q` to exercise save handling, menu settings, touch movement, collisions, and run rewards.

Audit and module-flow notes: [docs/PROJECT_AUDIT.md](docs/PROJECT_AUDIT.md), [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), and [docs/DEVELOPMENT_REPORT.md](docs/DEVELOPMENT_REPORT.md).

## Project layout

- `main.py`: launcher
- `engine/game.py`: game loop, input, collision orchestration, HUD, and screens
- `engine/assets.py`: package-aware spritesheet, animation, sprite, and background loader
- `engine/animation.py`: movement and timed reaction state controller
- `engine/patterns.py`: constrained procedural obstacle and pickup patterns
- `engine/progression.py`: missions, daily challenges, and achievements
- `engine/difficulty.py`: calm/standard speed and spawn curves
- `engine/analytics.py`: bounded run history, coaching, and adaptive pace
- `engine/replay.py`: capped ghost-run sampling
- `engine/worlds.py`: profile-level world palette/hazard catalog
- `engine/effects.py`: reduced-motion-aware bounded particles
- `engine/audio.py`: generated soundtrack and sound effects
- `database/save_manager.py`: SQLite persistence

## Replaceable art packs

The renderer accepts art shipped inside an installable Python package, or a local manifest file. This keeps art separate from game logic and lets a pack replace the runner animations, hazards, pickups, or city backdrop. The game uses Pygame-ce's sprite types and loads package resources through Python's standard `importlib.resources`; no art-specific runtime dependency is required.

Set `NEON_DASH_ASSET_PACK` before launching. For a package that includes `art/manifest.json`, use:

```powershell
$env:NEON_DASH_ASSET_PACK = "my_neon_art:art/manifest.json"
py main.py
```

For a local pack, point the same setting at its manifest file. Manifests map texture names to PNG files, animations to frame rectangles and frame rates, and sprite/background names to images or atlas regions. Runner animation names use the selected avatar ID plus `.run`, `.jump`, or `.slide` (for example `violet.run`). Hazard and pickup keys match the runtime entity kinds (`barrier`, `gate`, `electric_car`, `fence`, `coin`, `battery`, `shield`, `magnet`, `score_boost`, `overdrive`, and `coin_bonus`); a `city` background is scaled to the game window. Missing entries continue to use the built-in renderer.

Example atlas manifest:

```json
{
  "textures": {"characters": "sprites/characters.png"},
  "animations": {
    "runner.run": {
      "texture": "characters",
      "fps": 10,
      "frames": [[0, 0, 32, 48], [32, 0, 32, 48]]
    }
  },
  "sprites": {
    "coin": {"texture": "characters", "frame": [0, 48, 16, 16]}
  }
}
```
