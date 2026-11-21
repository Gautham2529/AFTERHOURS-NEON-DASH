# 🌃 AFTERHOURS: NEON DASH
### ⚡ Run the Loop. Dodge the Chaos. Beat Your Record.

An original three-lane arcade runner set above the **Meridian Loop**.

Dodge ion pylons, laser gates, electric fences, and runaway pulse cars. Collect tokens and boosters, activate powerful dashes, and build your high score as each run becomes progressively faster.

---

## 🧭 Navigate the Game

| Section | What's inside |
|:---|:---|
| 🎮 [Gameplay](#-gameplay) | Collectibles and boosters |
| ⌨️ [Controls](#-controls) | Keyboard and touch controls |
| 🚀 [Progression](#-progression-and-upgrades) | Upgrades and runner unlocks |
| 🌆 [Worlds](#-worlds-and-visual-effects) | Environments and visual effects |
| 🎵 [Audio](#-audio-system) | Music and sound effects |
| 💚 [Comfort](#-comfort-and-accessibility) | Accessibility and ghost runs |
| 🏆 [Missions](#-missions-challenges-and-records) | Challenges and achievements |
| 🧠 [Adaptive Gameplay](#-adaptive-gameplay-and-procedural-generation) | Procedural generation and analytics |
| 🎨 [Art Packs](#-replaceable-art-packs) | Custom assets |
| 🛠️ [Project Structure](#-project-structure) | Codebase overview |
| 🧪 [Testing](#-testing) | Run the test suite |

---

## 🚀 Get Started

**Ready to enter the Meridian Loop?**

Install the required dependencies and launch the game:

```powershell
py -m pip install -r requirements.txt
py main.py
```

---

## 🎮 Gameplay

The goal is simple: **survive as long as possible, avoid obstacles, collect tokens, and achieve the highest score.**

### ⚡ Collectibles & Boosters

| Collectible | What it does |
|:---|:---|
| 🪙 **Tokens** | Score points and become upgrade points after each run. |
| 🔋 **Batteries** | Charge the dash meter. |
| 🛡️ **Shields** | Absorb one collision. |
| 🧲 **Magnets** | Attract nearby tokens. |
| ✨ **Score Boosts** | Double score gains temporarily. |
| ⚡ **Overdrive** | Increases speed and distance. |
| 🟠 **Token Doubler** | Makes each collected token count twice for a limited time. |

> 💡 **First time playing?** The first run includes a short tutorial. The title screen also provides access to the upgrade garage and runner selection.

---

## ⌨️ Controls

<details>
<summary><b>🖥️ Keyboard Controls</b> · Click to expand</summary>

| Key | Action |
|:---|:---|
| `Left` / `A` | Switch to the left lane |
| `Right` / `D` | Switch to the right lane |
| `Up` / `W` / `Space` | Jump over ion pylons |
| `Down` / `S` | Slide under laser gates |
| `E` | Activate a full dash charge |
| `P` / `Esc` | Pause the game |
| `U` | Open upgrades |
| `C` | Open runner selection |
| `Enter` / `R` | Restart after a run |
| `M` | Mute or restore sound |
| `F11` | Toggle fullscreen and windowed mode |

</details>

<details>
<summary><b>📱 Touch Controls</b> · Click to expand</summary>

- Swipe left or right to change lanes.
- Swipe up to jump.
- Swipe down to slide.
- Enable large on-screen tap controls from **Comfort & Controls**.

</details>

---

## 🏁 Progression and Upgrades

**Run. Earn. Upgrade. Unlock. Repeat.**

Spend upgrade points to improve:

- 🧲 Magnet reach and duration.
- ⚡ Dash charge and duration.
- 🛡️ Shield capacity.
- 🪙 Token value.
- 🔋 Energy-cell strength.

Unlock and select four original runner avatars, each with a different ability.

### 📈 Player Progression

- Run levels increase as your score grows.
- Profile levels unlock additional content.
- Best score and best token count are saved.
- Upgrades and selected environments persist.
- Unlocked runners and player progress are stored locally using SQLite.

---

## 🌆 Worlds and Visual Effects

Explore different environments featuring:

<details>
<summary><b>🌍 Explore the Environments</b></summary>

- Neon city streets.
- Underground tunnels.
- Industrial districts.
- Rooftops.
- Markets.
- Highways.
- Arcade-inspired scenery.

</details>

Worlds feature animated parallax backgrounds, atmospheric effects, and transition lighting.

The runner uses procedural articulation, while dash trails, pickup bursts, glowing track lights, atmospheric haze, and subtle camera movement respond to the selected motion settings.

---

## 🎵 Audio System

Music and sound effects are synthesized by the game at startup. No downloaded audio assets are required.

**Audio features include:**

- Dynamically generated background music.
- Distinct sound effects for pickups.
- Layered, faster soundtrack states during boosters.
- Independent music and sound-effect volume controls.
- Rate-limited coin collection sounds.

---

## 💚 Comfort and Accessibility

The **Comfort & Controls** panel provides configurable options for:

| Setting | Description |
|:---|:---|
| Reduced motion | Configurable motion reduction |
| Reduced flashing | Configurable flashing reduction |
| Calm pace | Gentler gameplay pace |
| Music and effects | Independent volume controls |
| Blink reminders | Brief blink-break reminders |
| Touch buttons | Large on-screen controls |
| Swipe sensitivity | Adjustable swipe sensitivity |
| Adaptive pace | Adaptive gameplay pacing |
| Ghost preferences | Personal-best, previous-run, saved-run, or no ghost |

The default gameplay uses a gentler speed curve and wider obstacle spacing.

Blink reminders are brief and never pause gameplay. Rapidly repeated coin sounds are also rate-limited to reduce audio fatigue.

### 👻 Ghost Runs

Choose between:

- Personal-best ghost.
- Previous-run ghost.
- Saved-run ghost.
- No ghost.

Ghost runners act as non-colliding visual guides.

> When saved-run mode is selected, use the left and right controls on the selected row to choose from the five most recent replay tracks.

---

## 🏆 Missions, Challenges, and Records

The **Missions & Records** section includes several progression and replay systems.

<details>
<summary><b>🎯 Missions and Contracts</b></summary>

- Behavior-selected missions that can be completed in one run.
- Two adaptive career contracts that accumulate progress across multiple runs.

</details>

<details>
<summary><b>📅 Daily and Weekly Challenges</b></summary>

- Offline daily challenges.
- Offline weekly challenges.
- Challenge history tracking.
- Protection against duplicate reward claims when the system date moves backward.

</details>

<details>
<summary><b>🏅 Achievements and Statistics</b></summary>

- Lifetime achievements.
- Run statistics.
- Runner profiles.
- World selection.
- Challenge history.

</details>

Mission, career-contract, daily, weekly, and achievement rewards can only be claimed once. Reward claims are stored with the player's profile.

---

## 🧠 Adaptive Gameplay and Procedural Generation

The game includes systems designed to make runs challenging while maintaining fair gameplay.

| System | Function |
|:---|:---|
| Procedural patterns | Generates constrained obstacle and pickup patterns. |
| Lane safety | Single-lane hazards leave two lanes open. |
| Reaction window | Live hazard crossing times are checked against the player's reaction window. |
| Pattern variety | Repeated lane patterns are reduced. |
| Local telemetry | Records recent runs. |
| Post-run coaching | Provides basic performance feedback. |
| Adaptive pace | Uses recent gameplay data to adjust difficulty. |

### 🎨 Unlockable Variants

Profile progression also unlocks **seven visual and audio variants**, including palette, scenery, hazard, and music changes that rotate during longer runs.

---

## 🎨 Replaceable Art Packs

The renderer supports replaceable art packs shipped through an installable Python package or a local manifest file.

This separates visual assets from the game logic and allows art packs to replace:

- Runner animations.
- Hazard sprites.
- Pickup sprites.
- City backgrounds.

The asset system uses Pygame-ce sprite types and Python's standard `importlib.resources` module. No additional art-specific runtime dependency is required.

### 📦 Loading an Asset Pack

Set the `NEON_DASH_ASSET_PACK` environment variable before launching the game.

<details>
<summary><b>🐍 Python package asset pack</b></summary>

For a Python package containing `art/manifest.json`:

```powershell
$env:NEON_DASH_ASSET_PACK = "my_neon_art:art/manifest.json"
py main.py
```

</details>

<details>
<summary><b>📁 Local asset pack</b></summary>

For a local asset pack, point the same environment variable to its manifest file.

</details>

### 🗂️ Asset Manifest

Manifests define:

- Textures and their PNG file locations.
- Animation frames and frame rates.
- Sprite images and atlas regions.
- Background images.

Runner animation names use the selected avatar ID followed by `.run`, `.jump`, or `.slide`.

For example:

```text
violet.run
violet.jump
violet.slide
```

Hazard and pickup keys match the runtime entity types:

```text
barrier
gate
electric_car
fence
coin
battery
shield
magnet
score_boost
overdrive
coin_bonus
```

A `city` background is scaled to fit the game window.

<blockquote>

**Fallback support:** Missing asset entries automatically fall back to the built-in renderer.

</blockquote>

<details>
<summary><b>🔍 View Example Atlas Manifest</b></summary>

```json
{
  "textures": {
    "characters": "sprites/characters.png"
  },
  "animations": {
    "runner.run": {
      "texture": "characters",
      "fps": 10,
      "frames": [
        [0, 0, 32, 48],
        [32, 0, 32, 48]
      ]
    }
  },
  "sprites": {
    "coin": {
      "texture": "characters",
      "frame": [0, 48, 16, 16]
    }
  }
}
```

</details>

---

## 🛠️ Project Structure

<details>
<summary><b>📂 View Project Directory</b></summary>

```text
AFTERHOURS-NEON-DASH/
│
├── main.py
├── requirements.txt
│
├── engine/
│   ├── game.py
│   ├── assets.py
│   ├── animation.py
│   ├── patterns.py
│   ├── progression.py
│   ├── difficulty.py
│   ├── analytics.py
│   ├── replay.py
│   ├── worlds.py
│   ├── effects.py
│   └── audio.py
│
├── database/
│   └── save_manager.py
│
├── docs/
│   ├── PROJECT_AUDIT.md
│   ├── ARCHITECTURE.md
│   └── DEVELOPMENT_REPORT.md
│
└── tests/
```

</details>

### ⚙️ Core Modules

| File | Responsibility |
|:---|:---|
| `main.py` | Game launcher |
| `engine/game.py` | Game loop, input, collision orchestration, HUD, and screens |
| `engine/assets.py` | Package-aware spritesheet, animation, sprite, and background loader |
| `engine/animation.py` | Movement and timed reaction state controller |
| `engine/patterns.py` | Procedural obstacle and pickup pattern generation |
| `engine/progression.py` | Missions, daily challenges, and achievements |
| `engine/difficulty.py` | Calm and standard speed and spawn curves |
| `engine/analytics.py` | Run history, coaching, and adaptive pace |
| `engine/replay.py` | Capped ghost-run sampling |
| `engine/worlds.py` | Profile-level world, palette, and hazard catalog |
| `engine/effects.py` | Reduced-motion-aware particle effects |
| `engine/audio.py` | Generated soundtrack and sound effects |
| `database/save_manager.py` | SQLite-based player data persistence |

---

## 🧪 Testing

Run the test suite using:

```powershell
python -m pytest -q
```

The tests cover:

- Save handling.
- Menu settings.
- Touch movement.
- Collision detection.
- Run rewards.
- Asset loading and fallback behavior.
- Replay and gameplay-related systems.

---

## 📚 Documentation

Want to understand what's happening behind the scenes?

| Document | Description |
|:---|:---|
| 📋 [Project Audit](docs/PROJECT_AUDIT.md) | Project audit |
| 🏗️ [Architecture](docs/ARCHITECTURE.md) | Architecture |
| 📝 [Development Report](docs/DEVELOPMENT_REPORT.md) | Development report |

---

<p align="center">

### 🌃 AFTERHOURS: NEON DASH

**The Meridian Loop never sleeps. Neither does your high score.**

</p>