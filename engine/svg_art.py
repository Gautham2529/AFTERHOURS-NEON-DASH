"""Cached SVG artwork rasterized to Pygame surfaces."""

from __future__ import annotations

import math
from collections import OrderedDict
from functools import lru_cache
from io import BytesIO

import pygame


_SCALED: OrderedDict[tuple[int, int, int], tuple[pygame.Surface, pygame.Surface]] = OrderedDict()
_SCALED_CAPACITY = 128


def _hex(color: tuple[int, int, int]) -> str:
    red, green, blue = (max(0, min(255, int(value))) for value in color)
    return f"#{red:02x}{green:02x}{blue:02x}"


def _document(width: int, height: int, content: str) -> str:
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
            f'viewBox="0 0 {width} {height}">{content}</svg>')


@lru_cache(maxsize=256)
def _render(markup: str) -> pygame.Surface:
    surface = pygame.image.load(BytesIO(markup.encode("utf-8")), "neon-dash.svg")
    if pygame.display.get_surface() is not None:
        surface = surface.convert_alpha()
    return surface


def scaled(surface: pygame.Surface, size: tuple[int, int]) -> pygame.Surface:
    """Smooth-scale artwork through a bounded cache."""
    width, height = max(1, int(size[0])), max(1, int(size[1]))
    key = (id(surface), width, height)
    cached = _SCALED.get(key)
    if cached is not None and cached[0] is surface:
        _SCALED.move_to_end(key)
        return cached[1]
    result = pygame.transform.smoothscale(surface, (width, height))
    _SCALED[key] = (surface, result)
    if len(_SCALED) > _SCALED_CAPACITY:
        _SCALED.popitem(last=False)
    return result


@lru_cache(maxsize=7)
def sky_surface(sky: tuple[int, int, int], accent: tuple[int, int, int]) -> pygame.Surface:
    """Create a layered night sky with a luminous horizon and a distant moon."""
    content = [
        ('<defs><linearGradient id="nightSky" x1="0%" y1="0%" x2="0%" y2="100%">'
         '<stop offset="0" stop-color="#050817"/>'
         f'<stop offset=".58" stop-color="{_hex(sky)}"/>'
         '<stop offset="1" stop-color="#1a102f"/>'
         '</linearGradient></defs>'),
        '<rect width="960" height="285" fill="url(#nightSky)"/>',
        '<ellipse cx="474" cy="279" rx="520" ry="118" fill="#9328bd" fill-opacity=".12"/>',
        f'<ellipse cx="460" cy="275" rx="360" ry="72" fill="{_hex(accent)}" fill-opacity=".10"/>',
        '<ellipse cx="755" cy="77" rx="56" ry="56" fill="#ec51c1" fill-opacity=".07"/>',
        '<circle cx="755" cy="77" r="31" fill="#e88de1" fill-opacity=".68"/>',
        f'<circle cx="766" cy="67" r="29" fill="{_hex(sky)}"/>',
        '<path d="M0 260 Q210 238 430 264 T960 252 V285 H0 Z" fill="#7a2c9c" fill-opacity=".10"/>',
    ]
    for index in range(48):
        x = (index * 193 + 37) % 960
        y = 16 + (index * 71 + 23) % 205
        radius = 1 if index % 4 else 2
        color = "#c8faff" if index % 3 else "#ff91dc"
        content.append(
            f'<circle cx="{x}" cy="{y}" r="{radius}" fill="{color}" '
            f'fill-opacity="{.34 if index % 3 else .54}"/>'
        )
    for index in range(4):
        x = 105 + index * 245
        content.append(
            f'<path d="M{x} 0 H{x + 16} L{x + 83} 265 H{x - 46} Z" '
            f'fill="{_hex(accent)}" fill-opacity=".025"/>'
        )
    return _render(_document(960, 285, "".join(content)))


def _window_column_markup(
    window_x: int,
    column: int,
    context: tuple[int, int, int, int],
    accent: tuple[int, int, int],
) -> str:
    top, base_y, style, index = context
    parts = []
    for row, window_y in enumerate(range(top + 17, base_y - 8, 19)):
        if (window_x * 11 + window_y * 5 + index) % 5 == 0:
            continue
        color = accent if (column + row + style) % 4 else (255, 85, 173)
        opacity = ".78" if (column + row) % 3 else ".38"
        parts.append(
            f'<rect x="{window_x - 2}" y="{window_y - 2}" width="7" height="11" '
            f'fill="{_hex(color)}" fill-opacity=".09"/>'
            f'<rect x="{window_x}" y="{window_y}" width="4" height="8" '
            f'fill="{_hex(color)}" fill-opacity="{opacity}"/>'
        )
    return "".join(parts)


def _window_markup(
    building: tuple[int, int, int, int],
    base_y: int,
    index: int,
    accent: tuple[int, int, int],
) -> str:
    x, building_width, building_height, style = building
    top = base_y - building_height
    step = 13 if building_width < 48 else 15
    context = (top, base_y, style, index)
    return "".join(
        _window_column_markup(window_x, column, context, accent)
        for column, window_x in enumerate(range(x + 7, x + building_width - 5, step))
    )


def _facade_markup(
    building: tuple[int, int, int, int],
    base_y: int,
    fill: str,
    accent: str,
    edge: str,
) -> str:
    x, width, height, _style = building
    top = base_y - height
    return (
        f'<path d="M{x},{base_y} V{top + 8} L{x + 8},{top} '
        f'H{x + width - 5} L{x + width},{top + 7} V{base_y} Z" '
        f'fill="{fill}" stroke="{accent}" stroke-opacity=".16" stroke-width="1"/>'
        f'<path d="M{x + 5},{top + 10} H{x + width - 5}" '
        f'stroke="{edge}" stroke-opacity=".55" stroke-width="2"/>'
    )


def _roof_markup(
    building: tuple[int, int, int, int],
    index: int,
    base_y: int,
    accent: tuple[int, int, int],
) -> str:
    x, width, height, style = building
    top = base_y - height
    parts = []
    if style == 1:
        antenna_x = x + width // 2
        parts.append(
            f'<path d="M{antenna_x},{top} V{top - 15}" stroke="{_hex(accent)}" '
            'stroke-opacity=".8" stroke-width="2"/>'
        )
    elif style == 2 and width > 48:
        sign_y = min(base_y - 18, top + 36)
        parts.extend((
            f'<path d="M{x + 6},{sign_y} H{x + width - 6} V{sign_y + 12} '
            f'H{x + 6} Z" fill="#10152b" stroke="{_hex(accent)}" '
            'stroke-opacity=".72" stroke-width="1.5"/>',
            f'<path d="M{x + 11},{sign_y + 6} H{x + width - 11}" '
            f'stroke="{_hex(accent)}" stroke-width="2" stroke-opacity=".9"/>',
        ))
    if width > 64:
        rail_color = accent if index % 2 else (255, 85, 173)
        parts.extend((
            f'<path d="M{x + 5},{base_y - 6} V{top + 22}" stroke="{_hex(rail_color)}" '
            'stroke-opacity=".66" stroke-width="2"/>',
            f'<path d="M{x + width - 5},{base_y - 6} V{top + 22}" '
            f'stroke="{_hex(accent)}" stroke-opacity=".44" stroke-width="2"/>',
        ))
    return "".join(parts)


def _building_markup(
    building: tuple[int, int, int, int],
    index: int,
    base_y: int,
    skyline: tuple[int, int, int],
    accent: tuple[int, int, int],
) -> str:
    _x, _width, _height, style = building
    shade = 62 + (style % 3) * 9
    base = tuple(min(255, round(channel * shade / 100)) for channel in skyline)
    edge = tuple(min(255, channel + 24) for channel in base)
    return (_facade_markup(building, base_y, _hex(base), _hex(accent), _hex(edge))
            + _window_markup(building, base_y, index, accent)
            + _roof_markup(building, index, base_y, accent))


@lru_cache(maxsize=32)
def skyline_surface(
    buildings: tuple[tuple[int, int, int, int], ...],
    width: int,
    base_y: int,
    palette: tuple[tuple[int, int, int], tuple[int, int, int]],
    height: int | None = None,
) -> pygame.Surface:
    """Build a transparent, detailed city strip from deterministic building data."""
    skyline, accent = palette
    height = base_y if height is None else height
    content = "".join(
        _building_markup(building, index, base_y, skyline, accent)
        for index, building in enumerate(buildings)
    )
    return _render(_document(width, height, content))


@lru_cache(maxsize=16)
def entity_surface(kind: str) -> pygame.Surface | None:
    """Return vector artwork for a recognized runner entity."""
    shared = {
        "coin": ('<circle cx="48" cy="48" r="31" fill="#8f4d15" stroke="#ffe597" stroke-width="4"/>'
                 '<circle cx="48" cy="48" r="24" fill="#ffc94e" stroke="#fff4b1" stroke-width="3"/>'
                 '<path d="M48 28 L64 48 L48 68 L32 48 Z" fill="#fff0a0"/>'
                 '<path d="M48 34 V62 M39 48 H57" stroke="#c27c22" stroke-width="4"/>'),
        "battery": ('<rect x="27" y="23" width="42" height="57" rx="8" fill="#103b58" '
                    'stroke="#63eaf2" stroke-width="4"/><path d="M39 17 H57 V25 H39 Z" fill="#63eaf2"/>'
                    '<path d="M52 32 L38 54 H48 L43 70 L61 47 H51 Z" fill="#ffe17a"/>'
                    '<path d="M31 75 H65" stroke="#ff5db5" stroke-width="3"/>'),
        "shield": ('<path d="M48 14 L76 25 V48 Q72 69 48 84 Q24 69 20 48 V25 Z" '
                   'fill="#113c48" stroke="#68f2c8" stroke-width="5"/>'
                   '<path d="M48 25 L65 32 V48 Q62 61 48 71 Q34 61 31 48 V32 Z" '
                   'fill="#1b6170" stroke="#a2ffe4" stroke-width="2"/>'),
        "magnet": ('<path d="M29 24 V49 A19 19 0 0 0 67 49 V24" fill="none" '
                   'stroke="#ff5db5" stroke-width="15" stroke-linecap="round"/>'
                   '<path d="M29 22 V39 M67 22 V39" stroke="#fff2fa" stroke-width="5"/>'
                   '<path d="M25 19 H39 V39 H25 Z M57 19 H71 V39 H57 Z" '
                   'fill="#432454" stroke="#ff8bc8" stroke-width="2"/>'),
        "score_boost": ('<circle cx="48" cy="48" r="33" fill="#463417" stroke="#ffd65e" stroke-width="4"/>'
                        '<path d="M25 35 H48 Q57 35 57 43 Q57 48 51 53 L41 60 H59 V67 H25 '
                        'V60 L46 44 H25 Z" fill="#fff4b4"/>'
                        '<path d="M63 37 L70 45 L77 37 L80 42 L73 50 L80 58 L76 63 L69 55 '
                        'L62 63 L58 58 L65 50 L58 42 Z" fill="#ffc94e"/>'),
        "overdrive": ('<circle cx="48" cy="48" r="33" fill="#103a58" stroke="#61e9fa" stroke-width="4"/>'
                      '<path d="M53 17 L31 50 H45 L39 79 L67 41 H51 Z" '
                      'fill="#b8fbff" stroke="#29b9e3" stroke-width="2"/>'),
        "coin_bonus": ('<circle cx="48" cy="48" r="33" fill="#482c22" stroke="#ffad54" stroke-width="4"/>'
                       '<circle cx="48" cy="48" r="23" fill="none" stroke="#ffd77c" stroke-width="2"/>'
                       '<path d="M25 36 H45 Q52 36 52 43 Q52 47 47 51 L37 58 H53 V64 H24 '
                       'V59 L42 46 H25 Z" fill="#fff2c7"/>'
                       '<path d="M75 41 Q71 35 64 39 Q58 43 58 51 Q58 59 64 62 Q71 65 76 59 '
                       'L72 55 Q69 59 65 57 Q63 55 63 51 Q63 46 66 44 Q69 42 72 46 Z" '
                       'fill="#ffcc72"/>'),
        "barrier": ('<path d="M14 39 L22 25 H74 L82 39 V76 H14 Z" fill="#1b334d" '
                    'stroke="#72ecf0" stroke-width="4"/>'
                    '<path d="M23 33 H73 V43 H23 Z" fill="#ff579e"/>'
                    '<path d="M24 50 H72 V67 H24 Z" fill="#10243c" stroke="#426b83" stroke-width="2"/>'
                    '<path d="M18 72 H78" stroke="#ffce6b" stroke-width="4"/>'
                    '<circle cx="25" cy="38" r="3" fill="#fff0a8"/>'
                    '<circle cx="71" cy="38" r="3" fill="#fff0a8"/>'),
        "gate": ('<path d="M17 79 V24 H79 V79" fill="none" stroke="#43cfe8" stroke-width="9"/>'
                 '<path d="M18 43 H78" stroke="#ff4fbe" stroke-width="7"/>'
                 '<path d="M24 43 H72" stroke="#ffc2ef" stroke-width="2"/>'
                 '<circle cx="17" cy="24" r="6" fill="#b9fbff"/>'
                 '<circle cx="79" cy="24" r="6" fill="#b9fbff"/>'),
        "fence": ('<path d="M18 24 V82 M78 24 V82" stroke="#4fe0ef" stroke-width="7"/>'
                  '<path d="M21 37 H75 M21 52 H75 M21 67 H75" stroke="#ff57bb" stroke-width="4"/>'
                  '<path d="M21 37 H75 M21 67 H75" stroke="#c3fbff" stroke-opacity=".72" stroke-width="1.5"/>'
                  '<circle cx="18" cy="24" r="6" fill="#d3ffff"/>'
                  '<circle cx="78" cy="24" r="6" fill="#d3ffff"/>'),
        "electric_car": ('<path d="M15 58 L22 41 Q25 35 33 33 L40 21 H65 L76 40 L84 47 V69 H15 Z" '
                         'fill="#142f4d" stroke="#55d9ec" stroke-width="4"/>'
                         '<path d="M38 27 H62 L69 41 H30 Z" fill="#69d9ea" fill-opacity=".76"/>'
                         '<path d="M20 53 H79" stroke="#ff5da9" stroke-width="4"/>'
                         '<circle cx="31" cy="70" r="8" fill="#101626" stroke="#f8c965" stroke-width="3"/>'
                         '<circle cx="68" cy="70" r="8" fill="#101626" stroke="#f8c965" stroke-width="3"/>'
                         '<path d="M43 49 H57" stroke="#d4ffff" stroke-width="3"/>'),
        "train": ('<rect x="19" y="18" width="58" height="65" rx="13" fill="#172f4d" '
                  'stroke="#60dfed" stroke-width="4"/>'
                  '<rect x="27" y="27" width="42" height="23" rx="5" fill="#68d9e8" fill-opacity=".68"/>'
                  '<path d="M24 59 H72" stroke="#ff5caa" stroke-width="5"/>'
                  '<circle cx="31" cy="74" r="4" fill="#ffce68"/>'
                  '<circle cx="65" cy="74" r="4" fill="#ffce68"/>'),
    }
    content = shared.get(kind)
    return _render(_document(96, 96, content)) if content is not None else None


def _runner_limb_markup(pose: str, frame: int) -> tuple[str, str, str]:
    if pose == "jump":
        left_leg, right_leg = "M33 58 L23 67 L29 71", "M50 58 L60 65 L67 62"
        left_arm, right_arm = "M31 36 L19 26 L15 17", "M52 36 L64 26 L69 17"
        left_foot, right_foot = (24, 71), (68, 62)
    else:
        stride = math.sin(frame * math.tau / 8)
        left_knee = (round(30 + stride * 5), round(69 - abs(stride) * 2))
        right_knee = (round(51 - stride * 5), round(69 + abs(stride) * 2))
        left_foot, right_foot = (round(30 + stride * 9), 79), (round(55 - stride * 9), 79)
        left_leg = f"M33 59 L{left_knee[0]} {left_knee[1]} L{left_foot[0]} {left_foot[1]}"
        right_leg = f"M50 59 L{right_knee[0]} {right_knee[1]} L{right_foot[0]} {right_foot[1]}"
        left_arm = f"M31 36 L{round(24 - stride * 5)} 44 L{round(20 - stride * 7)} 52"
        right_arm = f"M52 36 L{round(59 + stride * 5)} 44 L{round(63 + stride * 7)} 52"

    legs = (
        f'<path d="{left_leg} {right_leg}" fill="none" stroke="#141c31" '
        'stroke-width="11" stroke-linecap="round" stroke-linejoin="round"/>'
        f'<path d="{left_leg} {right_leg}" fill="none" stroke="url(#suit)" '
        'stroke-width="5" stroke-linecap="round" stroke-linejoin="round"/>'
    )
    arms = (
        f'<path d="{left_arm} {right_arm}" fill="none" stroke="#27324a" '
        'stroke-width="9" stroke-linecap="round" stroke-linejoin="round"/>'
        f'<path d="{left_arm} {right_arm}" fill="none" stroke="url(#suit)" '
        'stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/>'
    )
    shoes = (
        f'<path d="M{left_foot[0] - 6} {left_foot[1]} H{left_foot[0] + 5} '
        f'M{right_foot[0] - 5} {right_foot[1]} H{right_foot[0] + 6}" '
        'stroke="#f7c971" stroke-width="5" stroke-linecap="round"/>'
    )
    return legs, arms, shoes


@lru_cache(maxsize=64)
def runner_surface(
    jacket: tuple[int, int, int],
    trim: tuple[int, int, int],
    hair: tuple[int, int, int],
    pose: str,
    frame: int,
) -> pygame.Surface:
    """Create one cached runner pose with vector limbs and neon suit details."""
    jacket_hex, trim_hex, hair_hex = _hex(jacket), _hex(trim), _hex(hair)
    frame = frame % 8
    if pose == "slide":
        content = (
            '<ellipse cx="46" cy="75" rx="38" ry="5" fill="#030916" fill-opacity=".7"/>'
            '<path d="M22 51 L66 42 L79 56 L39 66 Z" fill="#101b33" stroke="#46dce8" stroke-width="3"/>'
            f'<path d="M31 48 L65 40 L73 51 L40 59 Z" fill="{jacket_hex}"/>'
            f'<path d="M35 48 L62 42" stroke="{trim_hex}" stroke-width="4"/>'
            '<path d="M28 58 L12 72 M48 61 L33 78" stroke="#26334b" stroke-width="8" stroke-linecap="round"/>'
            '<path d="M29 59 L13 72 M49 62 L34 78" stroke="#82eaf0" stroke-width="3" stroke-linecap="round"/>'
            '<path d="M67 43 L80 35" stroke="#27334b" stroke-width="7" stroke-linecap="round"/>'
            '<path d="M75 41 L87 37" stroke="#f0b997" stroke-width="4" stroke-linecap="round"/>'
            '<circle cx="79" cy="30" r="10" fill="#efb996" stroke="#ffe0bf" stroke-width="2"/>'
            f'<path d="M69 29 Q70 16 84 19 L91 26 L88 31 L74 27 Z" fill="{hair_hex}"/>'
            f'<path d="M50 49 L66 45" stroke="{trim_hex}" stroke-width="2"/>'
        )
        return _render(_document(96, 84, content))

    legs, arms, shoes = _runner_limb_markup(pose, frame)
    content = (
        '<ellipse cx="43" cy="83" rx="24" ry="4" fill="#030916" fill-opacity=".58"/>'
        f'{legs}{shoes}'
        '<path d="M29 32 Q42 25 55 33 L57 59 Q43 66 29 59 Z" fill="#111d36" '
        'stroke="#6f819b" stroke-width="2"/>'
        f'<path d="M32 34 Q43 29 53 35 L54 56 Q43 61 32 56 Z" fill="url(#suit)"/>'
        f'<path d="M34 40 L51 36" stroke="{trim_hex}" stroke-width="4"/>'
        '<path d="M31 54 L54 54" stroke="#bafcff" stroke-opacity=".78" stroke-width="2"/>'
        f'{arms}'
        '<circle cx="17" cy="55" r="4" fill="#efb996"/>'
        '<circle cx="64" cy="54" r="4" fill="#efb996"/>'
        '<path d="M36 13 Q38 7 47 8 Q57 10 57 20 L55 31 Q47 36 37 30 Z" '
        'fill="#efb996" stroke="#ffe0bf" stroke-width="1.5"/>'
        f'<path d="M34 17 Q33 5 46 4 Q57 5 60 14 L57 19 L42 15 L37 22 Z" fill="{hair_hex}"/>'
        '<path d="M47 22 H55" stroke="#fff2da" stroke-width="2"/>'
        '<path d="M30 33 L25 39 L30 43" fill="none" stroke="#79f0f0" stroke-width="2"/>'
        f'<path d="M51 34 L56 42" stroke="{trim_hex}" stroke-width="3"/>'
    )
    if pose == "shield":
        content += '<circle cx="43" cy="43" r="40" fill="none" stroke="#72f5d2" stroke-opacity=".58" stroke-width="3"/>'
    elif pose == "dash":
        content += '<path d="M5 46 H22 M8 54 H24" stroke="#74f6ff" stroke-opacity=".74" stroke-width="3"/>'
    definitions = (
        '<defs><linearGradient id="suit" x1="0" y1="0" x2="1" y2="1">'
        f'<stop offset="0" stop-color="{_hex(tuple(min(255, channel + 38) for channel in jacket))}"/>'
        f'<stop offset=".56" stop-color="{jacket_hex}"/>'
        f'<stop offset="1" stop-color="{_hex(tuple(max(0, channel - 35) for channel in jacket))}"/>'
        '</linearGradient></defs>'
    )
    return _render(_document(88, 88, definitions + content))


@lru_cache(maxsize=128)
def panel_surface(
    width: int,
    height: int,
    fill: tuple[int, int, int],
    outline: tuple[int, int, int],
) -> pygame.Surface:
    """Create a beveled holographic panel with a restrained neon edge."""
    width, height = max(12, width), max(12, height)
    fill_hex, edge_hex = _hex(fill), _hex(outline)
    bevel = min(12, max(4, height // 5), max(4, width // 8))
    path = (f"M{bevel},1 H{width - bevel - 4} L{width - 1},{bevel + 3} "
            f"V{height - bevel - 3} L{width - bevel - 4},{height - 1} "
            f"H{bevel} L1,{height - bevel - 3} V{bevel + 3} Z")
    content = (
        f'<path d="{path}" fill="{fill_hex}" stroke="{edge_hex}" stroke-width="2"/>'
        f'<path d="M{bevel + 4},5 H{width - bevel - 10}" stroke="{edge_hex}" '
        'stroke-opacity=".28" stroke-width="1"/>'
        f'<path d="M5,{height - 7} H{width // 3}" stroke="{edge_hex}" '
        'stroke-opacity=".32" stroke-width="1"/>'
        f'<path d="M{width - 25},5 H{width - bevel - 7} L{width - 6},{bevel + 3}" '
        f'fill="none" stroke="{edge_hex}" stroke-width="2"/>'
        f'<circle cx="{bevel + 1}" cy="{bevel + 1}" r="2" fill="{edge_hex}"/>'
    )
    return _render(_document(width, height, content))


@lru_cache(maxsize=64)
def glow_surface(color: tuple[int, int, int], size: int = 32) -> pygame.Surface:
    """Return a compact, transparent, layered glow sprite."""
    size = max(4, min(128, int(size)))
    center = size / 2
    circles = []
    for fraction, opacity in ((.49, .035), (.37, .055), (.25, .085), (.13, .16)):
        circles.append(
            f'<circle cx="{center:g}" cy="{center:g}" r="{size * fraction:g}" '
            f'fill="{_hex(color)}" fill-opacity="{opacity}"/>'
        )
    return _render(_document(size, size, "".join(circles)))
