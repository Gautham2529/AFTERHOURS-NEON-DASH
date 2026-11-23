# AFTERHOURS Architecture

## Runtime flow

`main.py` constructs `NeonRunner` and enters a Pygame-ce loop. Each frame reads events, updates the active state with a capped delta, draws the city/track and active screen, then flips the display.

```text
main.py
└─ NeonRunner (engine/game.py)
   ├─ AudioBus (engine/audio.py)
   ├─ AssetPack / AnimatedSprite (engine/assets.py)
   ├─ PatternGenerator (engine/patterns.py)
   ├─ DifficultyCurve (engine/difficulty.py)
   ├─ mission/achievement definitions (engine/progression.py)
   └─ SaveManager (database/save_manager.py) → profile row + normalized analytics tables
```

## Responsibilities

- `engine/game.py` owns screen state, input routing, player/run state, collision outcomes, HUD, and screen composition. It coordinates systems but still contains a large amount of rendering code.
- `engine/svg_art.py` rasterizes reusable SVG scenery, perspective roads, entities, runner poses, panels, and glow sprites to cached Pygame surfaces. Rasterization and size-specific smooth scaling happen on first use; subsequent draws reuse bounded caches.
- `engine/patterns.py` makes one pattern at a time. Hazard patterns block one lane and keep the other two open; recent lane/kind history reduces repeated patterns. Before accepting a hazard row, it simulates active and candidate hazard crossing times at current movement speed and checks a bounded reaction/lane-switch window; after bounded rerolls it can leave a gap.
- `engine/difficulty.py` contains calm/standard speed and spawn-interval curves with bounded adaptive multipliers.
- `engine/analytics.py` stores bounded local run summaries and lane preference, calculates a conservative play-style hint, and adjusts difficulty gradually from observed success/reaction inputs.
- `engine/animation.py` selects physics-independent locomotion and timed reaction states; `engine/assets.py` resolves those through manifest clips with procedural fallback.
- `engine/replay.py` samples personal-best, previous, and up to five archived runs at 20 Hz, with a 90-second per-run cap. The comfort screen selects archived tracks; the displayed guide is a simple non-colliding silhouette.
- `engine/worlds.py` defines seven level-gated procedural environments and per-world hazard pools; the player can select unlocked environments, which rotate every 5,000 metres during play. `engine/parallax.py` draws cached, deterministic SVG skyline strips at separate speeds and freezes motion when reduced motion is enabled.
- `engine/effects.py` bounds pickup particle count, adds cached vector glow sprites, and suppresses particles in reduced-motion mode.
- Graphics quality is split into persisted glow, particle, reflection, and atmosphere switches. Each effect is gated independently at draw/emission time so low-power Intel Iris Xe systems can reduce cost without changing simulation state.
- `engine/progression.py` defines behavior-selected one-run missions, two adaptive multi-run career contracts with persisted progress, rotating offline daily/weekly objectives, and lifetime achievements with one-time reward evaluation.
- `engine/assets.py` loads cached atlas textures (including SVG where supported by the installed Pygame-ce image loader) from local files or Python package resources. `AnimatedSprite` uses Pygame's sprite base class. Missing art falls through to the built-in SVG/procedural renderer.
- `engine/audio.py` generates music and effects in memory and applies separate music/effects levels, environment motifs, booster state, and coin rate limiting.
- `database/save_manager.py` writes the compatibility profile row plus queryable `analytics_totals`, `analytics_meta`, and `run_summaries` tables in SQLite. Legacy JSON analytics migrate atomically on load; `load()` reconstructs the familiar profile mapping for the game. The runner tags the profile payload with a schema version, validates known fields, and retains unknown keys for forward/legacy data preservation.

## Persistence shape

The profile includes score records, wallet, upgrades, runner unlocks, profile XP, comfort settings, lifetime counters, claimed missions/achievements, daily and weekly objective progress/history, adaptive difficulty preference, personal-best/previous ghost samples, a capped five-run ghost archive, and selected environment. Bounded run summaries and aggregates have dedicated SQLite tables; a legacy `analytics` field is imported from older JSON saves on load. Older payloads without newer fields use defaults. Unknown fields are copied through on save. The payload is tagged `schema_version: 4`; this is a compatibility marker, not a migration framework for arbitrary future schema changes.

## Input map

- Keyboard: arrows/A-D for lanes, W/up/space for jump, S/down for slide, E for dash, P/Escape to pause.
- Touch: horizontal/vertical swipes; optional on-screen buttons include left, jump, slide, right, dash. A lower-right tap pauses. Touch gestures are accepted when the game reports finger events.
- Mouse: screen/menu rows, touch buttons when enabled, pause resume, and game-over restart.

## Current boundaries

The window size and frame cap are constants. The main module still owns several intertwined systems and is a candidate for incremental extraction. No external art pack is shipped or selected; the built-in scene combines cached SVG art with Pygame-drawn motion and effects. Pattern validation covers lane availability and repeated lane streaks; it does not simulate every possible player reaction timing or certify all long-run sequences. Environment differences use procedural palettes and details rather than unique authored art packs, and the replay guide remains a silhouette.
