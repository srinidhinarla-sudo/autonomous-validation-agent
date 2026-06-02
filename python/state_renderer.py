"""
State renderer — generates simple PNG mockups of infotainment UI states.

Used by visual regression tests to detect unintended state-name or layout
changes between builds.  Requires Pillow.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Dict, Tuple

try:
    from PIL import Image, ImageDraw, ImageFont  # type: ignore
    _PIL_AVAILABLE = True
except ImportError:
    _PIL_AVAILABLE = False

try:
    import infotainment_sm as sm
    _SM_AVAILABLE = True
except ImportError:
    _SM_AVAILABLE = False

# ---- colour palette per subsystem ----------------------------------------
_SUBSYSTEM_COLOURS: Dict[str, Tuple[int, int, int]] = {
    "BOOT":         (20, 20, 20),
    "HOME":         (30, 50, 100),
    "RADIO":        (80, 20, 80),
    "NAV":          (20, 80, 60),
    "PHONE":        (20, 60, 120),
    "MEDIA":        (100, 40, 20),
    "SETTINGS":     (50, 50, 50),
    "CLIMATE":      (20, 90, 90),
    "PARK_ASSIST":  (90, 60, 20),
    "VEHICLE_INFO": (40, 70, 40),
    "APPS":         (70, 30, 90),
    "NOTIFICATION": (100, 80, 0),
    "VOICE":        (0, 80, 100),
    "CHARGING":     (0, 100, 60),
    "DRIVER":       (80, 40, 60),
    "AMBIENT":      (60, 0, 100),
    "ERROR":        (120, 0, 0),
}

_WIDTH, _HEIGHT = 480, 270
_FONT_SIZE = 18
_SMALL_FONT = 12


def _bg_colour(state_name: str) -> Tuple[int, int, int]:
    for prefix, colour in _SUBSYSTEM_COLOURS.items():
        if state_name.startswith(prefix):
            return colour
    return (40, 40, 40)


def _load_font(size: int):
    try:
        return ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", size)
    except Exception:
        try:
            return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", size)
        except Exception:
            return ImageFont.load_default()


def render_state(state, output_path: str | Path) -> Path:
    """
    Render a simple UI mockup for *state* and save it as a PNG.

    Returns the path to the saved file.
    """
    if not _PIL_AVAILABLE:
        raise ImportError("Pillow is required for visual regression tests. "
                          "pip install Pillow")
    if not _SM_AVAILABLE:
        raise ImportError("infotainment_sm module not built.")

    state_str = sm.state_name(state)
    bg = _bg_colour(state_str)

    img = Image.new("RGB", (_WIDTH, _HEIGHT), color=bg)
    draw = ImageDraw.Draw(img)

    font_big   = _load_font(_FONT_SIZE)
    font_small = _load_font(_SMALL_FONT)

    # Title bar
    draw.rectangle([(0, 0), (_WIDTH, 40)], fill=(0, 0, 0))
    draw.text((10, 10), "Infotainment HMI", font=font_big, fill=(200, 200, 200))

    # State label
    draw.text((20, 60), state_str, font=font_big, fill=(255, 255, 255))

    # Subsystem indicator strip
    subsystem = state_str.split("_")[0]
    draw.rectangle([(0, _HEIGHT - 25), (_WIDTH, _HEIGHT)], fill=(0, 0, 0, 180))
    draw.text((10, _HEIGHT - 20), f"Subsystem: {subsystem}", font=font_small,
              fill=(150, 200, 150))

    # Simple "status bar" icons
    draw.rectangle([(10, 90), (60, 110)],  outline=(100, 100, 100), width=1)
    draw.text((12, 92), "SIG",  font=font_small, fill=(100, 200, 100))
    draw.rectangle([(70, 90), (120, 110)], outline=(100, 100, 100), width=1)
    draw.text((72, 92), "BT",   font=font_small, fill=(100, 150, 255))
    draw.rectangle([(130, 90), (180, 110)], outline=(100, 100, 100), width=1)
    draw.text((132, 92), "WIFI", font=font_small, fill=(100, 200, 100))

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(str(output_path))
    return output_path


def render_all_states(output_dir: str | Path) -> Dict[str, Path]:
    """Render PNGs for every state.  Returns {state_name: path}."""
    if not _SM_AVAILABLE:
        raise ImportError("infotainment_sm module not built.")
    output_dir = Path(output_dir)
    paths: Dict[str, Path] = {}
    for name in sm.InfotainmentStateMachine.all_state_names():
        if name == "STATE_COUNT":
            continue
        state = getattr(sm.State, name)
        p = render_state(state, output_dir / f"{name}.png")
        paths[name] = p
    return paths


def image_hash(path: str | Path) -> str:
    """SHA-256 of a PNG file — used as a fast equality check."""
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def pixel_diff(path_a: str | Path, path_b: str | Path) -> Tuple[int, float]:
    """
    Returns (differing_pixels, percentage).
    Requires Pillow.
    """
    if not _PIL_AVAILABLE:
        raise ImportError("Pillow required.")
    from PIL import ImageChops
    img_a = Image.open(str(path_a)).convert("RGB")
    img_b = Image.open(str(path_b)).convert("RGB")
    diff  = ImageChops.difference(img_a, img_b)
    total = img_a.width * img_a.height
    differing = sum(1 for p in diff.getdata() if any(c > 10 for c in p))
    return differing, 100.0 * differing / total
