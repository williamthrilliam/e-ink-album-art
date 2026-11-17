"""Color conversion for the 13.3" Spectra 6 panel.

The Waveshare driver's built-in conversion (epd13in3E.getbuffer) snaps each pixel to the
six *ideal* sRGB primaries (pure #00ff00 green, #0000ff blue, ...). Real Spectra 6 inks are
much duller, so that conversion tends to over-estimate how bright and saturated the panel can
be. This module instead error-diffuses against a palette that describes how the inks actually
look (CIELAB), using the `epaper-dithering` library, then packs the result for the panel.

It is only used when `"color_mode": "dither"` is set in config/config.json, so the legacy
path (driver quantize) is untouched and still the default.

Optional config keys:
    color_mode    "legacy" (default) or "dither"
    palette_path  path to an `epaper-palette` JSON file (default: config/palette.json)
    dither        dict of epaper_dithering.DitherOptions fields, e.g.
                  {"mode": "floyd_steinberg", "tone": 0.2, "gamut": 0.3}
"""

import os

import numpy as np
from PIL import Image

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_PALETTE_PATH = os.path.join(BASE_DIR, "config", "palette.json")

# Color codes the panel expects for each ink (see epd13in3E.EPD: BLACK=0, WHITE=1,
# YELLOW=2, RED=3, BLUE=5, GREEN=6; code 4 is not used by the panel).
PANEL_CODES = {"black": 0, "white": 1, "yellow": 2, "red": 3, "blue": 5, "green": 6}

DEFAULT_DITHER = {"mode": "floyd_steinberg"}

_palette_cache = {}


def load_palette(path=None):
    """Load (and cache) the palette plus the lookup table from palette index to panel code."""
    from epaper_dithering import Palette

    path = path or DEFAULT_PALETTE_PATH
    if not os.path.isabs(path):
        path = os.path.join(BASE_DIR, path)
    if path in _palette_cache:
        return _palette_cache[path]

    palette = Palette.load(path)
    if len(palette) != len(PANEL_CODES):
        raise ValueError(
            f"{path}: expected exactly the {len(PANEL_CODES)} Spectra 6 inks, found {len(palette)} entries"
        )
    lut = np.zeros(len(palette), dtype=np.uint8)
    for name, code in PANEL_CODES.items():
        index = palette.index_of(name)
        if index is None:
            raise ValueError(f"{path}: palette has no ink named '{name}'")
        lut[index] = code

    _palette_cache[path] = (palette, lut)
    return palette, lut


def dither_to_indices(image, config=None):
    """Dither an RGB image; returns (palette-index image in mode 'P', palette, lut)."""
    from epaper_dithering import DitherOptions, dither_image

    config = config or {}
    palette, lut = load_palette(config.get("palette_path"))
    options = dict(DEFAULT_DITHER)
    options.update(config.get("dither", {}))
    return dither_image(image.convert("RGB"), palette, DitherOptions(**options)), palette, lut


def pack_codes(codes):
    """Pack an (H, W) array of panel color codes two pixels per byte, as the driver expects."""
    if codes.shape[1] % 2:
        raise ValueError("image width must be even")
    packed = (codes[:, 0::2].astype(np.uint8) << 4) | codes[:, 1::2].astype(np.uint8)
    return packed.ravel().tolist()


def canvas_to_buffer(canvas, config, panel_size):
    """Convert a full-panel RGB canvas to the packed buffer that `epd.display()` takes.

    `panel_size` is (epd.width, epd.height). Like the driver's getbuffer, a canvas that is the
    transposed size is rotated 90 degrees; any other size is an error.
    """
    width, height = panel_size
    if canvas.size == (height, width):
        canvas = canvas.rotate(90, expand=True)
    if canvas.size != (width, height):
        raise ValueError(f"Invalid image dimensions: {canvas.size}, expected {(width, height)}")

    indexed, _palette, lut = dither_to_indices(canvas, config)
    return pack_codes(lut[np.asarray(indexed)])
