# Development and Validation Report

Date: 2026-11-21 (client local date).

## Implementation since the audit baseline

- Added startup validation for malformed progression fields and clamped saved upgrade levels to their defined limits.
- Preserved unknown legacy save keys, added a schema version marker, and kept corrupted JSON/non-object saves recoverable as a fresh profile.
- Fixed a stale asset animation that could display the previous avatar when the selected animation was absent.
- Added atlas crop/scale caching with a bounded scaled-image cache and corrected city-background layering.
- Extracted deterministic difficulty curves and constrained pattern generation. Each hazard pattern blocks a single lane; recent lane history prevents three identical lane selections in succession.
- Added offline daily challenges, one-run missions, lifetime achievements, statistics/profile pages, and one-time point rewards.
- Added touch dash, touch pause, functional pause mouse resume, and generated jump/slide cues.
- Retained old standalone prototype/config/art files; they were not removed.
- Added bounded local run telemetry and up to 100 saved run summaries, observed collision/pickup/avoidance metrics, and post-run coaching based on the recent history.
- Added gradual adaptive speed/spawn tuning with relaxed, balanced, and challenge preferences; the multiplier is bounded and saved.
- Added 20 Hz personal-best and previous-run ghost replay with a 90-second sample cap, a three-mode setting, and non-interactive translucent character rendering.
- Added seven profile-level environments with distinct procedural skyline details, palettes, hazard pools, and music; the active palette rotates every 5,000 m among unlocked worlds, and an explicit world-select screen respects unlock levels.
- Added a small, reduced-motion-aware animated rain layer and environment-specific synthesized backing motifs.
- Added an offline weekly challenge with ISO-week rotation, cumulative local progress, and a one-time weekly reward.
- Added measured reaction windows and near-miss counts to run telemetry; those inputs feed the bounded adaptive pace model.
- Added capped pickup particles that are suppressed in reduced-motion mode; reduced flashing and swipe sensitivity are independently configurable. Added distinct passive abilities to three selectable avatars.
- Added a reusable animation-state controller for locomotion, jump preparation/fall/landing, dash, hit, shield, pickup, defeat, and milestone states. Corrected the jump arc to use its actual configured duration.
- Added a token doubler power-up, difficulty-aware mission templates, a challenge-history page, date-rollback reward protection, and richer post-run/statistics summaries.
- Added dynamic music intensity and a rate-limited near-miss cue; analytics now feed mission selection and end-of-run difficulty adjustment.
- Bumped the additive save marker to schema 4 and persist analytics, settings, ghosts, difficulty preference, selected environment, mission history, and challenge history while retaining unknown legacy keys.
- Rebalanced the comfort screen to include adaptive pace and ghost visibility.
- Added transactional, normalized SQLite tables for aggregate analytics and up to 100 run summaries, including per-run difficulty history; legacy JSON analytics migrate on first load and the game retains its compatibility profile interface.
- Adaptive difficulty now incorporates measured jump, slide, lane-change escape, and dash outcomes alongside run success, reaction windows, and recent consistency.
- Added deterministic, repeating far/mid pixel skyline layers with separate scroll rates; reduced-motion mode freezes their movement without removing scenery.
- Added a reaction-time route validator to obstacle spawning. It models hazard crossing times at current speed, lane-switch timing, existing active hazards, and a conservative minimum reaction window; unsafe candidates are rerolled, with an empty row as the exhausted fallback.
- Added a five-run replay archive selectable from the persisted ghost comfort control; best, previous, saved-run, and off modes preserve the existing save interface, and left/right selects archived runs.
- Added adaptive career contracts for cumulative distance, tokens, dash clears, clean moves, pickups, and evasions. Two active contracts retain cross-run progress, change only when completed, select from recent play behavior, and award one-time persisted rewards.

## Bug reproductions and repairs

| Reproduction scenario | Root cause | Repair | Regression evidence |
| --- | --- | --- | --- |
| Start with `upgrades="corrupt"`, an invalid avatar collection, and a nonnumeric wallet | Loader trusted the shape/type of values inside otherwise valid JSON | Validate known fields, clamp counters/levels, filter avatar IDs | Regression test failed with `ValueError` before fix and passes afterward |
| Select an animation absent from the configured art pack after displaying another avatar | `AnimatedSprite` retained its previous frame when lookup returned `None` | Clear image and bounds on a missing frame so procedural fallback draws | Regression test failed before fix and passes afterward |
| Click the visible pause overlay's Resume button | Mouse hit area did not match the button; old region could restart the run | Align resume/restart hitboxes with rendered buttons | Regression test confirms run state and score are preserved |
| Run through a sequence of generated obstacles | Completely random lane selection could repeat the same blocked lane indefinitely | Track recent lane/kind history and enforce a single blocked lane per pattern | 500 seeded patterns checked for valid lanes, open routes, and no three-lane streak |
| Load custom city background | Opaque fallback sky and skyline covered the supplied image | Skip those fallback layers when custom city art exists | Pixel-level background layering regression passes |
| Call run finalization twice | Rewards could be applied more than once if a future caller repeats the transition | Make finalization idempotent and track claimed goal IDs | Test confirms mission, achievement, and wallet rewards do not duplicate |
| Roll the system clock back to a previously rewarded daily/weekly period | Only the most recent claim flag was checked | Keep a bounded completion history and consult it during startup | Regression case restores saved state at a prior date and verifies both claims stay closed |
| Load malformed analytics or unsorted ghost samples | Nested summary values and sample order were trusted | Normalize bounded analytics fields and sort/validate replay frames | Corrupt-value and replay-boundary tests pass |
| Build an upcoming obstacle row that removes every safe route or leaves too little lane-switch time | Generation validated each row in isolation and never considered currently active hazards | Simulate crossing times and reaction windows before accepting a generated hazard; reroll then leave an empty row if no safe option is found | Regressions check a reachable sequence, simultaneous three-lane block, insufficient reaction time, and spawn fallback |
| Select a saved ghost after finishing runs | Only best/previous streams were retained, and replay selection had no archive state | Keep a capped five-run archive with score/distance metadata and persistent comfort selection | Integration test finishes two runs, selects each replay, draws one, reconstructs the runner from the persisted profile, and verifies the selected stream |
| Open the comfort screen with an archived replay selected | The first instruction string extended underneath the right-aligned run label | Shorten the helper copy to keep the instructions and selected-run value in separate columns | Inspected before/after 960x540 comfort renders; final capture is `docs/visual_qc_ghost_archive.png` |
| Make partial career-contract progress and start another run | The first selector draft rotated contracts each run, and completion checked totals by metric instead of contract ID | Keep unfinished contracts active and compare cumulative progress by stable mission key | Reproduction failed on the second run before the correction; the regression now verifies persistence, completion, one-time reward, and restored state |
| Add two career contracts to the mission screen | The compact seven-row layout centered status lines over detail text | Increase row spacing and move progress/reward labels lower inside each card | Inspected the corrected 960x540 render at `docs/visual_qc_missions.png`; gameplay integration test draws the page |
| Inspect a legacy save for actual SQLite analytics tables | Analytics were only nested inside the profile JSON blob | Reproduce missing `run_summaries` table, then add transactional schema-backed aggregates/run rows and first-load migration | Regression demonstrated `no such table: run_summaries` before fix; migration and compatibility tests pass |
| Change lanes to dodge a nearby hazard and then steer into another occupied lane | Lane input count had no outcome evidence for adaptive pacing | Measure hazard-window lane-change attempts and count success only if the destination is clear | Paired regression cases distinguish successful escape from blocked destination |

## Automated test results

- Pre-change baseline: 14 tests passed.
- Final suite: 62 tests passed, including SQLite migration, bounded analytics/save validation, adaptive difficulty, route-aware obstacle generation, archived ghost selection, multi-run career progress, replay boundaries, world locks, mission selection, animation transitions, accessibility settings, power-up effects, challenge rollback protection, parallax, and screen rendering.
- Latest performance test after mission integration: 240 offscreen gameplay update/draw iterations, run separately from the suite; mean 2.07 ms, p95 2.60 ms in the current Windows/Python/Pygame-ce environment. Earlier separate passes ranged up to 3.70 ms mean and 8.53 ms p95, showing noticeable host timing variance.

The timing result measures software rendering to an offscreen/dummy display and excludes physical display presentation, GPU/driver behavior, and input latency. It is not a measured on-device 60-FPS guarantee.

## Manual visual inspection

A live Pygame window was launched, but the automation surface could not read its accessibility state. Fresh 960x540 frames rendered through the same Pygame renderer were inspected: `docs/visual_qc_gameplay.png` shows the layered skyline, track, runner, hazards/pickups, and HUD; `docs/visual_qc_ghost_archive.png` shows the selected-run comfort row; `docs/visual_qc_missions.png` shows the one-run and cumulative mission cards with progress labels separated. These are renderer captures, not screenshots from the inaccessible live window. Menus and pause flow were not manually inspected live. The world selector, challenge-history screen, and post-run summary remain draw-tested rather than freshly inspected.

## Known limitations / not complete

- No third-party art pack or external licensed art is included/configured. The active game still uses its built-in procedural artwork; the package-ready loader is infrastructure for plugging art in.
- There is no Windows executable/package build, configurable window size/frame cap, controller support, or formal database migration framework.
- Daily objectives rotate offline by local date and weekly objectives by ISO week; both catalogs remain small fixed sets. Mission/achievement content and the economy are intentionally compact and have not been playtested for long-term balance.
- The fifteen systems are integrated to different depths. This matrix records the current boundaries:

| Directive item | Current evidence | Status / remaining gap |
| --- | --- | --- |
| Adaptive difficulty | bounded factor uses reaction, avoidance, collisions, run success, selected pace | Implemented locally; model is explainable rules, not trained ML |
| Fair obstacle generation | deterministic seeded generation, route simulation across live hazards, speed-based crossing times, reaction/lane-switch window, safe fallback | Partial; conservative lane-only model does not simulate detailed jump/slide timing or prove all possible long sequences |
| Dynamic worlds | seven unlockable procedural environments, detail variants, palette/hazard/audio transitions, two depth-scrolling skyline layers | Partial; environments share a procedural scene grammar and have no authored unique scene art |
| Character animation | reusable controller and Pygame manifest frames with fallback | Partial; procedural fallback has limited frames and victory is not used by this endless mode |
| Context-aware power-ups | magnet, shield, score, battery, overdrive, token doubler, upgrade and sound feedback | Implemented for current set; long-term balance remains untested |
| Ghost replay | personal-best/previous and five archived run tracks, saved-run picker, playback toggle, bounded sampling, non-collision rendering | Partial; guide is procedural silhouette and replay follows sampled poses rather than event-perfect physics |
| Player analytics | bounded SQLite `run_summaries` and `analytics_totals`; stats UI, input/collision/power-up and per-run difficulty metrics; legacy payload migration | Partial; no event-level raw telemetry or dedicated analysis charts, and historical records are capped at 100 |
| Intelligent missions | behavior-selected one-run missions plus two persisted multi-run contracts; recent action history influences contract selection | Partial; finite compact catalog and simple selection heuristics, with long-term balance not playtested |
| Character abilities | balanced dash, coin-charge, and magnet-reach variants | Partial; cosmetics and unique avatar animations are absent |
| Dynamic audio | environment motifs, speed/danger intensity, booster layer, rate-limited cue | Partial; intensity mix is simple and not a layered adaptive score system |
| Game feel | smoothing, pickup particles, near-miss feedback, reactions, reduced motion | Partial; no screen shake or combo chain, effects remain intentionally restrained |
| Daily/weekly challenges | offline date/week rotation, cumulative weekly progress, history, rollback-safe rewards | Implemented for a compact fixed catalog |
| Post-run coaching | measured score, survival, collisions, action accuracy, power-ups, recent trend | Partial; advice is heuristic and should be treated as a prompt, not diagnosis |
| Unlockable environments | level gates, persisted selection, world select, palette/hazard/audio identity | Partial; no gameplay modifiers beyond hazard pool and visuals/audio |
| Accessibility/comfort | calm pace, reduced motion/flashing, audio controls, touch/swipe sensitivity, pause, breaks | Partial; no color-vision presets or remappable controls |

- No third-party art pack or external licensed art is included/configured. The active fallback remains procedural; package-ready loading supports user-supplied packs.
- Coaching is based on action counts and collision labels. Hazard attribution is improved at collision time, but recommendations remain coarse heuristics.
- Pattern tests prove basic lane availability and repetition limits; they do not formally prove every multi-pattern sequence is avoidable under all input timings.
- Performance timing is synthetic offscreen measurement only, not an integrated-graphics hardware run.
