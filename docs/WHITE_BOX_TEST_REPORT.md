# Graphics White-Box Test Report

## Scope

The report covers the focused graphics modules:

- `engine/svg_art.py`
- `engine/effects.py`
- `engine/parallax.py`

## Coverage result

Measured with Coverage.py branch analysis:

| Module | Statements | Missed | Branches | Partial branches | Coverage |
|---|---:|---:|---:|---:|---:|
| `engine/svg_art.py` | 181 | 0 | 40 | 0 | 100% |
| `engine/effects.py` | 53 | 0 | 26 | 0 | 100% |
| `engine/parallax.py` | 32 | 0 | 6 | 0 | 100% |

## White-box test techniques

- **Statement coverage:** Every executable statement in the three focused modules is executed.
- **Branch coverage:** Every true/false edge reported by Coverage.py is exercised, including cache hits, cache misses, reflection on/off, reduced-motion, glow on/off, and entity/pose fallbacks.
- **Path coverage:** The SVG, road, runner-pose, particle-emission, particle-update, and parallax test paths cover the independent runtime branches. Enumerating every combinatorial value path is not practical for the complete game, so path claims are scoped to the focused graphics modules.
- **Conditional coverage:** Both sides of conditional expressions are tested, including clamp bounds, positive/negative cache edges, known/unknown entities, and quality-setting branches.
- **Loop testing:** Tests exercise zero-iteration, normal-iteration, bounded-iteration, cache-eviction, repeated-frame, and full-pool states.
- **Data-flow testing:** Tests verify that values defined in one stage are consumed correctly in later stages, especially SVG cache keys to rasterized surfaces, scaled-size values to cached results, particle position/velocity/life fields through update and draw, and parallax distance/offset values through rendering.

## Reproduction

```powershell
python -m pytest -q --cov=engine.svg_art --cov=engine.effects --cov=engine.parallax --cov-branch --cov-config=.coveragerc --cov-report=term-missing tests/test_assets.py tests/test_runner_systems.py tests/test_parallax.py
```
