#!/usr/bin/env python3
"""Preview how the legacy and dithered conversions look, without touching the panel.

Both conversions are drawn with the same palette appearance (the inks' measured colors in
config/palette.json), so differences come from the conversion, not from the preview. The preview
is only as accurate as that palette: it is measured on a different Spectra 6 panel unless you
measure your own (see README).

Usage:
    python3 tools/compare_color.py INPUT [-o out.png] [--modes floyd_steinberg burkes ...]
                                   [--scale 1.875] [--detail X,Y]

INPUT is either album art (square; centred on the white canvas like display.py does) or an
already-rendered 1200x1600 canvas.
"""
import argparse
import os
import sys

import numpy as np
from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
import color_convert  # noqa: E402

W, H = 1200, 1600

# The driver's legacy palette: ideal primaries, index order black, white, yellow, red, (dup black), blue, green.
LEGACY_PALETTE = (0, 0, 0, 255, 255, 255, 255, 255, 0, 255, 0, 0, 0, 0, 0, 0, 0, 255, 0, 255, 0)
LEGACY_INK_BY_INDEX = {0: "black", 1: "white", 2: "yellow", 3: "red", 4: "black", 5: "blue", 6: "green"}


def make_canvas(path, scale):
    img = Image.open(path).convert("RGB")
    if img.size == (W, H):
        return img
    size = int(640 * scale)
    canvas = Image.new("RGB", (W, H), (255, 255, 255))
    img = img.resize((size, size), Image.Resampling.LANCZOS)
    canvas.paste(img, ((W - size) // 2, (H - size) // 2))
    return canvas


def legacy_preview(canvas, palette):
    pal = Image.new("P", (1, 1))
    pal.putpalette(LEGACY_PALETTE + (0, 0, 0) * 249)
    idx = np.asarray(canvas.quantize(palette=pal))
    preview = palette.preview_rgb()
    colors = np.array([preview[palette.index_of(LEGACY_INK_BY_INDEX[i])] for i in range(7)], dtype=np.uint8)
    return Image.fromarray(colors[idx], "RGB")


def new_preview(canvas, mode, palette_path, extra):
    cfg = {"palette_path": palette_path, "dither": dict(extra, mode=mode)}
    indexed, palette, _ = color_convert.dither_to_indices(canvas, cfg)
    return indexed.convert("RGB")


def label(img, text):
    img = img.copy()
    d = ImageDraw.Draw(img)
    d.rectangle((0, 0, 8 + 7 * len(text), 16), fill=(0, 0, 0))
    d.text((4, 2), text, fill=(255, 255, 255))
    return img


def parse_variant(text):
    """'label=mode,key=val,...' or 'mode,key=val' -> (label, options dict)."""
    label, _, spec = text.partition("=") if "=" in text.split(",")[0] else ("", "", text)
    opts = {}
    for i, part in enumerate(filter(None, spec.split(","))):
        if "=" not in part:
            opts["mode"] = part
            continue
        k, v = part.split("=")
        opts[k] = {"true": True, "false": False}.get(v, None)
        if opts[k] is None:
            try:
                opts[k] = float(v)
            except ValueError:
                opts[k] = v
    label = label or ",".join(f"{k}={v}" if k != "mode" else str(v) for k, v in opts.items())
    return label, opts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("-o", "--output", default="compare.png")
    ap.add_argument("--palette", default=color_convert.DEFAULT_PALETTE_PATH)
    ap.add_argument("--variant", action="append", default=[],
                    help="repeatable: [label=]mode[,key=value...]  e.g. 'fs tone=floyd_steinberg,tone=1'")
    ap.add_argument("--scale", type=float, default=1.875)
    ap.add_argument("--detail", default="450,350", help="x,y of a 200x200 crop (art coordinates) shown at 2x")
    ap.add_argument("--no-source", action="store_true")
    args = ap.parse_args()

    variants = [parse_variant(v) for v in (args.variant or ["floyd_steinberg", "burkes", "atkinson"])]
    canvas = make_canvas(args.input, args.scale)
    palette, _ = color_convert.load_palette(args.palette)

    panels = []
    if not args.no_source:
        panels.append(("source", canvas))
    panels.append(("legacy (ideal primaries)", legacy_preview(canvas, palette)))
    for label_, opts in variants:
        cfg = {"palette_path": args.palette, "dither": opts}
        indexed, _, _ = color_convert.dither_to_indices(canvas, cfg)
        panels.append(("new: " + label_, indexed.convert("RGB")))

    dx, dy = (int(v) for v in args.detail.split(","))
    ov, dt = [], []
    for name, im in panels:
        art = im.crop((0, 200, 1200, 1400)).resize((400, 400), Image.Resampling.LANCZOS)
        ov.append(label(art, name))
        crop = im.crop((dx, dy + 200, dx + 200, dy + 400)).resize((400, 400), Image.Resampling.NEAREST)
        dt.append(label(crop, name))
    sheet = Image.new("RGB", (400 * len(panels), 800), (255, 255, 255))
    for i, (a, b) in enumerate(zip(ov, dt)):
        sheet.paste(a, (400 * i, 0))
        sheet.paste(b, (400 * i, 400))
    sheet.save(args.output)
    print("wrote", args.output, sheet.size)


if __name__ == "__main__":
    main()
