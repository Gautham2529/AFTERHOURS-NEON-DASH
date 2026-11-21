# AFTERHOURS Project Audit

Audit baseline: 2026-11-21. This document records the existing project before the current master-prompt implementation work.

## Project map

```text
main.py
  └── engine.game.NeonRunner
       ├── engine.audio.AudioBus
       ├── engine.assets.AssetPack / AnimatedSprite
       └── database.save_manager.SaveManager ── SQLite

tests/
  ├── test_gameplay.py
  ├── test_assets.py
  └── test_save_manager.py
```

`metro_dash.py` is a separate Tkinter prototype with its own loop, collisions, and renderer. `config.py` and `engine/art.py` contain configuration/art helpers for the earlier RPG direction. None is imported by the active `main.py` runner. They are retained pending a deliberate archival/removal decision, as requested.

## What the active game currently does

- Runs a fixed 960×540, 60-FPS Pygame-ce endless runner.
- Supports three lanes, keyboard lane changes, jump, slide, dash, coins, five power-up families, collision cooldown, three-hit run termination, score, and increasing speed.
- Generates one-lane obstacle or pickup patterns with random spacing; patterns are not recorded, difficulty is not centrally modeled, and no automated fairness proof exists.
- Provides a tutorial, title menu, pause/game-over overlays, five upgrades, four selectable avatars, saved best scores/profile levels, and comfort settings.
- Supports touch swipes and optional on-screen lane/jump/slide buttons. Dash remains keyboard-only.
- Synthesizes music and effects; coin sound is quieter and rapid repeats are rate-limited.
- Saves one JSON payload in SQLite. Malformed JSON/non-object payloads are treated as absent; there is no schema version or migration mechanism.
- Can load optional spritesheets/animations/backgrounds from a local manifest or Python package. No third-party art pack is configured, so the active game still uses its code-drawn fallback art.

## Working and partially implemented areas

| Area | Current status |
| --- | --- |
| Core runner loop and keyboard play | Implemented; gameplay tests cover key state transitions. |
| Coins, power-ups, dash, upgrades, avatars | Implemented at a basic level; no broad balance or session testing yet. |
| Collision logic | Implemented with crossing checks and a hit cooldown; no automated combinations/fairness coverage. |
| Procedural generation | Produces a hazard in only one lane per hazard pattern, but has no history-aware repetition control or explicit safe-pattern validator. |
| Touch | Swipes and four optional buttons work for lane/jump/slide. Touch dash and a wider touch UI are missing. |
| Save handling | SQLite round-trip and malformed payload handling exist; individual field validation is incomplete and save schema is unversioned. |
| Audio | Generated music/SFX, volume controls, mute, booster layer, and coin rate limit exist. Playback/mixer failure and effect-priority tests are missing. |
| Visuals/assets | Art-pack infrastructure is implemented and tested in isolation; no real art pack is included/configured. Fallback runner, city, hazards, and UI remain primarily drawn from Pygame primitives. |
| Screens | Menu, tutorial, upgrade, avatar, comfort, pause, and game-over screens exist. Mission, achievement, statistics, and dedicated profile screens are missing. |
| Performance | Asset texture cache exists, but atlas crops and repeated transforms are not cached. No measured frame-time or memory report exists. |

## Risks and opportunities

1. `engine/game.py` owns input, simulation, generation, persistence coordination, and all screen rendering; separating data-driven progression/generation from presentation would improve testing without changing the game loop wholesale.
2. Save fields other than audio levels are not consistently validated. Bad `upgrades` or avatar collections can fail or behave incorrectly at startup.
3. Asset frame regions are cropped repeatedly; animation surfaces and scaled hazard art should be cached.
4. The optional background is drawn before opaque city/sky geometry and may be mostly obscured. An art pack needs an intentional layering contract and an end-to-end render test.
5. Current pattern tests do not establish a safe lane across combinations or ensure fair reaction spacing.
6. A Python package can carry data resources, but Pygame-ce itself does not provide a finished commercial art library. Art licensing/source and a concrete pack remain open; procedural fallback must remain usable offline.
7. The fixed window does not expose the requested configurable frame-rate or resize/scaling options.

## Preserve

- Existing runner controls, score rules, upgrades, character IDs, persisted progress keys, comfort options, and artwork fallback.
- `metro_dash.py`, `config.py`, and `engine/art.py` until their intended archival status is explicit and references have been rechecked.
- Offline operation and the current Pygame-ce/SQLite stack.

## Safe optimization candidates

- Validate/clamp save fields at the boundary.
- Cache atlas crops and resized art.
- Measure rendering before caching static visual layers; preserve reduced-motion effects and active booster state.
- Extract pure generation/score helpers into small modules only where tests benefit; avoid a broad rewrite of the already playable loop.

## Baseline tests

The previously run suite reported 14 passing tests. The current implementation pass will rerun the suite before and after changes; visual and performance claims will be reported separately from unit-test results.

## Implementation delta after the baseline

The active runner now also has a tested `PatternGenerator`, pure calm/standard difficulty curves, touch dash and pause, a records hub with missions/daily challenge/achievements/statistics/profile pages, saved one-time rewards, save-field validation, unknown-field preservation, and schema-version tagging. Asset atlas crops and scaled variants are cached, with a 128-entry LRU for transformed surfaces. The pause overlay mouse target and custom-background layering have regression coverage.

See [ARCHITECTURE.md](ARCHITECTURE.md) for module flow and [DEVELOPMENT_REPORT.md](DEVELOPMENT_REPORT.md) for bug reproductions, validation evidence, and open limitations. The art pack itself remains unconfigured, and the procedural fallback is still the visible default.
