"""graphics.py — A11 Information Graphics & Illustration Lead (P5/G3).

Deterministic Pillow drawing helpers for the 1024x1024 front page
(make.fun news-image-20261124, Tuesday 24 November 2026). BUILD v2.

API (all boxes are Pillow-style (x0, y0, x1, y1)):
    draw_scene(draw, box, story_id, palette) -> bool
        Flat code-drawn scene for one card story. Returns False for
        a6-01 (markets table card, no scene) and unknown ids.
        Scenes contain NO text. v2: badges sit OUTSIDE illustrations,
        so scenes use the full box. v3 port (previous design): red
        number chips overlay scenes bottom-left again — at the port
        feature boxes (172x30 / 168x30) each scene's focal element is
        shifted right/up clear of the chip zone (box-driven, h 28..32);
        lead scenes at 300x76 need no shift (focals sit high/right).
        Colour rules (A10 C8): NO red in scenes; NO region colours as
        scene identity — neutral palette only (navy, navy_light, gold,
        gold_light, ink, ink_soft, grey, paper, card, up-green).
    draw_world_map(draw, box, pins, palette, font=None, pin_radius=7.5)
        Real Natural Earth 110m coastline (public domain, embedded
        below as simplified data; no runtime network) + numbered pins.
        v2 (A10 B2): each pin is a Ø6px dot at the TRUE projected
        lat/lon (never moved) plus an 11px-bold number disc beside it;
        only the LABEL is offset on collision, with a 1px leader line
        when pushed to the outer ring. Pin colour = region colour
        (the one region-colour site in this module). pins: dicts with
        number, story_id, lon, lat (region optional; falls back to the
        baked-in story->region map from layout.json). pin_radius is
        kept for signature compatibility; dots are fixed Ø6px per B2.
        Header / legend / caption are A12's job (layout budgets exist).
    draw_markets_chart(draw, box, rows, palette, font=None)
        v2 (A10 C6): horizontal bar chart for the markets card.
        rows: copy.json feature_4 table_rows [{instrument, value,
        change}] (6 rows). Box 172x72 (pitch 12): instrument name
        (11px) left, bar proportional to % move (up = up-green,
        down = ink_soft; NO red per C8) around a visible zero line,
        "value change" text (11px) right-aligned.
    draw_timeline_axis(draw, box, pins, palette, font=None, hour_labels=True)
        UTC axis 00:00-24:00, ticks every 3h, dots at true pin times.
        pins: dicts with 'utc' "HH:MM" (preferred) or 'x_px'.

palette: the layout.json "palette" dict (values {"rgb": [...]}), a flat
{name: (r, g, b)} dict, the whole layout dict, or None (baked-in
defaults from layout.json). Colors used: palette + region colors and
their paper tints only. No randomness, no network, no external files
(fonts: caller-supplied, else Pillow default / system Liberation if
present — geometry is measured from the actual font at runtime).

Anti-aliasing (fix cycle 1b, user order): every public function renders
through _clipped, which supersamples at _SSAA=3 — the drawing runs on a
3x temp image via _ScaledDraw (all coordinates, line widths, radii and
font sizes scaled x3), then LANCZOS-downscales to the box size, so
circles, diagonals and polygon edges come out smooth, not pixelated.
"""

import math

from PIL import Image, ImageDraw, ImageFont

try:
    import numpy as _np
except ImportError:  # premultiply falls back to plain RGBA resize
    _np = None

_SSAA = 3  # supersampling factor for _clipped (1 = off)

# ---------------------------------------------------------------- palette

_DEFAULT_PALETTE = {
    "paper": (247, 243, 233), "paper2": (240, 234, 219),
    "card": (255, 253, 247), "card_edge": (205, 198, 180),
    "ink": (26, 26, 26), "ink_soft": (55, 52, 48),
    "grey": (100, 95, 86), "rule": (60, 56, 50),
    "navy": (27, 52, 92), "navy_light": (52, 84, 138),
    "red": (178, 24, 24), "red_dark": (140, 18, 18),
    "gold": (176, 141, 52), "gold_light": (216, 178, 84),
    "up": (18, 105, 45), "down": (178, 24, 24),
    "white": (255, 255, 255),
}

_REGION_COLORS = {
    "Europe": (27, 52, 92), "Middle East": (140, 18, 18),
    "Africa": (20, 102, 46), "East Asia": (91, 45, 142),
    "South & SE Asia": (11, 107, 106), "North America": (154, 71, 12),
    "South America": (122, 74, 33), "Oceania": (31, 111, 178),
    "Central Asia": (110, 59, 94), "Global": (74, 74, 74),
}

# story -> display region (from layout.json cards; pin color source)
_STORY_REGION = {
    "a4-01": "Middle East", "a6-04": "North America", "gap-01": "East Asia",
    "a6-01": "Global", "a6-02": "North America", "a5-03": "South & SE Asia",
    "a5-01": "East Asia", "a4-03": "Middle East", "a4-05": "Middle East",
    "a6-07": "Africa", "a6-08": "Africa", "gap-02": "Europe",
    "a6-06": "East Asia", "gap-04": "Europe",
}


def _rgb(c):
    if isinstance(c, dict):
        c = c.get("rgb", (0, 0, 0))
    return (int(c[0]), int(c[1]), int(c[2]))


def _pal(palette):
    """Normalize any accepted palette shape to flat {name: (r, g, b)}."""
    pal = dict(_DEFAULT_PALETTE)
    reg = dict(_REGION_COLORS)
    if isinstance(palette, dict):
        src = palette
        if "palette" in src and isinstance(src["palette"], dict):
            rc = src.get("region_colors")
            if isinstance(rc, dict):
                for k, v in rc.items():
                    reg[k] = _rgb(v)
            src = src["palette"]
        for k, v in src.items():
            if isinstance(k, str) and k.startswith("region:"):
                reg[k[7:]] = _rgb(v)
            elif k == "region_colors" and isinstance(v, dict):
                for rk, rv in v.items():
                    reg[rk] = _rgb(rv)
            else:
                try:
                    pal[k] = _rgb(v)
                except (TypeError, IndexError, KeyError):
                    pass
    pal["_regions"] = reg
    return pal


def _blend(c1, c2, f):
    return tuple(int(round(a + (b - a) * f)) for a, b in zip(c1, c2))


def _tint(pal, color, f):
    """Blend a palette color toward paper (f=1 -> paper)."""
    return _blend(color, pal["paper"], f)


def _region_color(pal, region):
    return pal["_regions"].get(region, pal["grey"])


def _font(font, size):
    if font is not None:
        return font
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def _sized_font(font, size, bold=False):
    """Font at >= size px: caller font resized via font_variant when
    too small (v2 legibility floor: pin labels + chart text 11px);
    else system Liberation/DejaVu if present; else Pillow default."""
    if font is not None:
        try:
            if font.size >= size:
                return font
            return font.font_variant(size=size)
        except (AttributeError, TypeError, ValueError):
            return font
    names = (("LiberationSans-Bold.ttf", "DejaVuSans-Bold.ttf") if bold
             else ("LiberationSans-Regular.ttf", "DejaVuSans.ttf"))
    for base in ("/usr/share/fonts/truetype/liberation/",
                 "/usr/share/fonts/truetype/dejavu/"):
        for name in names:
            try:
                return ImageFont.truetype(base + name, size)
            except (OSError, IOError):
                continue
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


# ---------------------------------------------------------------- helpers

class _ScaledDraw:
    """ImageDraw proxy that multiplies every coordinate, line width,
    radius and font size by a fixed factor (SSAA support for _clipped).

    Drawing code keeps working in logical (box) coordinates; the proxy
    scales geometry into the supersampled temp image. textbbox results
    are divided back to logical coordinates so caller arithmetic (pin
    labels, hour labels) stays in logical space. Anything not wrapped
    here delegates to the real draw object unchanged.
    """

    def __init__(self, draw, scale):
        self._d = draw
        self._s = scale

    def __getattr__(self, name):
        return getattr(self.__dict__["_d"], name)

    def _xy(self, xy):
        s = self._s
        if xy and isinstance(xy[0], (tuple, list)):
            return [(x * s, y * s) for x, y in xy]
        return [v * s for v in xy]

    def _kw(self, kw):
        if kw.get("width") is not None:
            kw["width"] = max(1, int(round(kw["width"] * self._s)))
        elif kw.get("outline") is not None:
            # Pillow's default outline width is 1px; scale it too so
            # outlines keep their logical weight after downscaling.
            kw["width"] = self._s
        return kw

    def _scaled_font(self, font):
        if font is None:
            return None
        try:
            return font.font_variant(
                size=max(1, int(round(font.size * self._s))))
        except (AttributeError, TypeError, ValueError):
            return font

    def rectangle(self, xy, **kw):
        return self._d.rectangle(self._xy(xy), **self._kw(kw))

    def rounded_rectangle(self, xy, radius=0, **kw):
        return self._d.rounded_rectangle(self._xy(xy), radius=radius * self._s,
                                          **self._kw(kw))

    def ellipse(self, xy, **kw):
        return self._d.ellipse(self._xy(xy), **self._kw(kw))

    def polygon(self, xy, **kw):
        return self._d.polygon(self._xy(xy), **self._kw(kw))

    def line(self, xy, **kw):
        return self._d.line(self._xy(xy), **self._kw(kw))

    def arc(self, xy, start, end, **kw):
        return self._d.arc(self._xy(xy), start, end, **self._kw(kw))

    def text(self, xy, text, font=None, **kw):
        return self._d.text(self._xy(xy), text,
                            font=self._scaled_font(font), **kw)

    def textbbox(self, xy, text, font=None, **kw):
        tb = self._d.textbbox(self._xy(xy), text,
                              font=self._scaled_font(font), **kw)
        s = self._s
        return tuple(v / s for v in tb)


def _downscale(img, size, transparent):
    """LANCZOS-downscale a supersampled temp image to box size.

    RGBA (transparent) images are alpha-premultiplied before resizing
    (numpy integer math, deterministic) so transparent black does not
    fringe into edge colors; without numpy it falls back to a plain
    RGBA resize.
    """
    if not transparent or _np is None:
        return img.resize(size, Image.LANCZOS)
    arr = _np.asarray(img).astype(_np.int32)
    a = arr[..., 3:4]
    arr[..., :3] = (arr[..., :3] * a + 127) // 255
    pm = Image.fromarray(arr.astype(_np.uint8), "RGBA")
    small = pm.resize(size, Image.LANCZOS)
    arr2 = _np.asarray(small).astype(_np.int32)
    a2 = arr2[..., 3:4]
    safe = _np.maximum(a2, 1)
    arr2[..., :3] = _np.clip((arr2[..., :3] * 255 + safe // 2) // safe,
                             0, 255)
    arr2[..., :3] = _np.where(a2 > 0, arr2[..., :3], 0)
    return Image.fromarray(arr2.astype(_np.uint8), "RGBA")


def _clipped(draw, box, fn, transparent=False):
    """Run fn(draw, box) clipped strictly to box (G-09: zero bleed).

    Renders into a temp image of box size and pastes it back, so no
    shape (Earth arc, gavel handle, map polygon, pin) can paint
    outside the box on the page image. Falls back to direct drawing
    if the ImageDraw has no accessible image.

    With _SSAA > 1 the temp image is rendered at _SSAA x box size
    (drawing code still sees logical coordinates via _ScaledDraw) and
    LANCZOS-downscaled before pasting — anti-aliased edges, same
    geometry, same zero-bleed guarantee.
    """
    x0, y0, x1, y1 = (float(v) for v in box)
    w, h = int(round(x1 - x0)), int(round(y1 - y0))
    img = getattr(draw, "_image", None)
    if img is None or w <= 0 or h <= 0:
        fn(draw, (x0, y0, x1, y1))
        return
    s = _SSAA
    if transparent:
        tmp = Image.new("RGBA", (w * s, h * s), (0, 0, 0, 0))
    else:
        tmp = Image.new("RGB", (w * s, h * s), (255, 255, 255))
    tdraw = ImageDraw.Draw(tmp)
    if s > 1:
        tdraw = _ScaledDraw(tdraw, s)
    fn(tdraw, (0.0, 0.0, float(w), float(h)))
    if s > 1:
        tmp = _downscale(tmp, (w, h), transparent)
    if transparent:
        img.paste(tmp, (int(round(x0)), int(round(y0))), tmp)
    else:
        img.paste(tmp, (int(round(x0)), int(round(y0))))


def _rel(box):
    x0, y0, x1, y1 = (float(v) for v in box)
    w, h = x1 - x0, y1 - y0
    return (lambda fx: x0 + fx * w), (lambda fy: y0 + fy * h), w, h


def _sky(draw, box, pal, sky_color, ground_color, horizon=0.80):
    x0, y0, x1, y1 = box
    hy = y0 + horizon * (y1 - y0)
    draw.rectangle([x0, y0, x1, hy], fill=sky_color)
    draw.rectangle([x0, hy, x1, y1], fill=ground_color)
    draw.line([x0, hy, x1, hy], fill=_blend(ground_color, pal["ink"], 0.25),
              width=1)
    return hy


def _starburst(draw, cx, cy, r, fill, inner=None):
    pts = []
    for i in range(16):
        ang = math.pi * i / 8.0
        rad = r if i % 2 == 0 else r * 0.45
        pts.append((cx + rad * math.cos(ang), cy + rad * math.sin(ang)))
    draw.polygon(pts, fill=fill)
    if inner is not None:
        r2 = r * 0.38
        draw.ellipse([cx - r2, cy - r2, cx + r2, cy + r2], fill=inner)


def _star4(draw, cx, cy, r, fill):
    pts = [(cx, cy - r), (cx + r * 0.28, cy - r * 0.28), (cx + r, cy),
           (cx + r * 0.28, cy + r * 0.28), (cx, cy + r),
           (cx - r * 0.28, cy + r * 0.28), (cx - r, cy),
           (cx - r * 0.28, cy - r * 0.28)]
    draw.polygon(pts, fill=fill)


def _fw_drone(draw, cx, cy, s, fill):
    """Fixed-wing drone silhouette pointing right (v2 B-order: NOT a
    quadcopter). s = half-length in px. Long fuselage, straight main
    wing, V-tail, nose sensor ball."""
    # fuselage (long + thin, satcom dome bump on top front)
    draw.polygon([(cx - s, cy - s * 0.07), (cx + s * 0.55, cy - s * 0.10),
                  (cx + s, cy - s * 0.01), (cx + s * 0.55, cy + s * 0.10),
                  (cx - s, cy + s * 0.07)], fill=fill)
    draw.ellipse([cx + s * 0.42, cy - s * 0.24, cx + s * 0.72, cy - s * 0.02],
                 fill=fill)
    # main wing (long, straight, narrow chord, mid-body)
    draw.polygon([(cx - s * 0.02, cy - s * 0.04), (cx + s * 0.16, cy - s * 0.04),
                  (cx + s * 0.20, cy + s * 0.62), (cx + s * 0.02, cy + s * 0.62)],
                 fill=fill)
    draw.polygon([(cx - s * 0.02, cy + s * 0.04), (cx + s * 0.16, cy + s * 0.04),
                  (cx + s * 0.20, cy - s * 0.62), (cx + s * 0.02, cy - s * 0.62)],
                 fill=fill)
    # inverted-V tail
    draw.polygon([(cx - s * 0.98, cy), (cx - s * 0.72, cy),
                  (cx - s * 0.60, cy - s * 0.40)], fill=fill)
    draw.polygon([(cx - s * 0.98, cy), (cx - s * 0.72, cy),
                  (cx - s * 0.60, cy + s * 0.40)], fill=fill)
    # nose sensor ball
    r = s * 0.13
    draw.ellipse([cx + s * 0.78 - r, cy + s * 0.10 - r,
                  cx + s * 0.78 + r, cy + s * 0.10 + r], fill=fill)


def _plane(draw, cx, cy, s, fill):
    """Simple jet silhouette pointing right; s = half-length in px."""
    pts = [(cx - s, cy + s * 0.10), (cx - s * 0.55, cy - s * 0.12),
           (cx + s * 0.55, cy - s * 0.14), (cx + s, cy),
           (cx + s * 0.55, cy + s * 0.14), (cx - s * 0.1, cy + s * 0.16),
           (cx - s * 0.35, cy + s * 0.42), (cx - s * 0.62, cy + s * 0.16),
           (cx - s * 0.95, cy + s * 0.34)]
    draw.polygon(pts, fill=fill)


def _dotted(draw, pts, color, r=1.2, step=5.0):
    """Dotted polyline through pts (list of (x, y))."""
    for (ax, ay), (bx, by) in zip(pts, pts[1:]):
        dist = math.hypot(bx - ax, by - ay)
        n = max(1, int(dist / step))
        for i in range(n + 1):
            t = i / n
            x, y = ax + (bx - ax) * t, ay + (by - ay) * t
            draw.ellipse([x - r, y - r, x + r, y + r], fill=color)


def _rot_rect(cx, cy, w, h, deg):
    a = math.radians(deg)
    ca, sa = math.cos(a), math.sin(a)
    return [(cx + dx * ca - dy * sa, cy + dx * sa + dy * ca)
            for dx, dy in ((-w / 2, -h / 2), (w / 2, -h / 2),
                           (w / 2, h / 2), (-w / 2, h / 2))]


# ---------------------------------------------------------------- scenes
# v2 (A10 C9/C8): specific scenes, no shared skyline template, NO red,
# NO region colours. Leads branch wide (455x56) vs compact (140x67);
# features branch strip (172x18 / 172x14, one icon) vs tall (regression
# boxes). Badges no longer overlay scenes: full box is usable.

def _burst(draw, cx, cy, r, pal):
    """Strike burst in gold/white (C8: red is reserved for brand)."""
    _starburst(draw, cx, cy, r, pal["gold"], pal["white"])


def _scene_riyadh(draw, box, pal):
    # a4-01: PIF Tower as a SLIM skyscraper + fixed-wing drone + burst.
    # Wide (455x56): tower focal right at ~90% of scene height.
    # Compact (140x67): tower focal centre-right.
    X, Y, w, h = _rel(box)
    x0, y0, x1, y1 = (float(v) for v in box)
    wide = w >= 5.0 * h
    hy = Y(0.78)
    draw.rectangle([x0, y0, x1, hy], fill=pal["navy_light"])
    draw.rectangle([x0, hy, x1, y1], fill=pal["gold"])
    draw.line([x0, hy, x1, hy], fill=pal["ink"], width=2)
    navy = pal["navy"]
    if wide:
        # few LOW wide blocks left (distinct from Shanghai skyline)
        for fx0, fx1, top, col in ((0.01, 0.13, 0.52, navy),
                                   (0.15, 0.30, 0.62, pal["ink_soft"]),
                                   (0.32, 0.42, 0.55, navy),
                                   (0.44, 0.58, 0.64, pal["ink_soft"]),
                                   (0.60, 0.70, 0.58, navy)):
            draw.rectangle([X(fx0), Y(top), X(fx1), hy], fill=col)
        tx0, tx1 = X(0.855), X(0.915)  # slim tower, focal right
        ttop, tbase = Y(0.05), Y(0.96)  # ~90% of scene height
        dcx, dcy = X(0.14), Y(0.16)
        path = [(dcx + w * 0.03, dcy + 2), (X(0.42), Y(0.10)),
                (X(0.70), Y(0.14)), (X(0.84), Y(0.10))]
    else:
        for fx0, fx1, top, col in ((0.01, 0.16, 0.55, navy),
                                   (0.18, 0.34, 0.66, pal["ink_soft"]),
                                   (0.36, 0.48, 0.58, navy)):
            draw.rectangle([X(fx0), Y(top), X(fx1), hy], fill=col)
        tx0, tx1 = X(0.63), X(0.75)  # slim tower, focal centre-right
        ttop, tbase = Y(0.08), Y(0.95)
        dcx, dcy = X(0.22), Y(0.18)
        path = [(dcx + w * 0.06, dcy + 2), (X(0.45), Y(0.12)),
                (X(0.60), Y(0.14))]
    taper = (tx1 - tx0) * 0.12
    draw.polygon([(tx0, tbase), (tx0 + taper, ttop), (tx1 - taper, ttop),
                  (tx1, tbase)], fill=pal["card"], outline=navy, width=2)
    draw.rectangle([tx0 + taper, ttop, tx1 - taper, ttop + h * 0.10],
                   fill=pal["gold_light"], outline=navy, width=2)
    for fy in (0.36, 0.50, 0.64):
        wy = Y(fy)
        draw.rectangle([(tx0 + tx1) / 2 - 2, wy, (tx0 + tx1) / 2 + 2, wy + 3],
                       fill=navy)
    _fw_drone(draw, dcx, dcy, w * (0.045 if wide else 0.11), pal["card"])
    _dotted(draw, path, pal["gold_light"], r=1.6, step=6.0)
    _burst(draw, (tx0 + tx1) / 2, ttop + h * 0.03, h * 0.17, pal)


def _scene_courthouse(draw, box, pal):
    # a6-04: courthouse (pediment + columns) + gavel, specific.
    X, Y, w, h = _rel(box)
    x0, y0, x1, y1 = (float(v) for v in box)
    wide = w >= 5.0 * h
    hy = Y(0.80)
    draw.rectangle([x0, y0, x1, hy], fill=pal["navy"])
    draw.rectangle([x0, hy, x1, y1], fill=pal["navy_light"])
    draw.line([x0, hy, x1, hy], fill=pal["ink"], width=2)
    navy, card = pal["navy"], pal["card"]
    if wide:
        bx0, bx1 = X(0.03), X(0.42)
        hx, hyy = X(0.72), Y(0.40)
        handle_to = (X(0.78), Y(0.72))
        block = (X(0.65), Y(0.78), X(0.86), Y(0.90))
        base = (X(0.68), Y(0.72), X(0.83), Y(0.79))
        head_w, head_h = w * 0.10, h * 0.34
    else:
        bx0, bx1 = X(0.04), X(0.56)
        hx, hyy = X(0.80), Y(0.32)
        handle_to = (X(0.85), Y(0.74))
        block = (X(0.70), Y(0.80), X(0.93), Y(0.92))
        base = (X(0.74), Y(0.74), X(0.89), Y(0.81))
        head_w, head_h = w * 0.22, h * 0.26
    apex_y, base_y = Y(0.06), Y(0.26)
    draw.polygon([(bx0, base_y), ((bx0 + bx1) / 2, apex_y), (bx1, base_y)],
                 fill=pal["gold"], outline=pal["ink"], width=2)
    cxm = (bx0 + bx1) / 2
    r = h * 0.055
    draw.ellipse([cxm - r, apex_y + h * 0.10, cxm + r, apex_y + h * 0.10 + 2 * r],
                 fill=navy)
    draw.rectangle([bx0, base_y, bx1, base_y + h * 0.09], fill=card,
                   outline=pal["ink"], width=2)
    col_top = base_y + h * 0.09
    col_bot = hy - h * 0.12
    cw = (bx1 - bx0) * 0.11
    for i in range(4):
        cx0 = bx0 + (bx1 - bx0) * (0.09 + i * 0.24)
        draw.rectangle([cx0, col_top, cx0 + cw, col_bot], fill=card,
                       outline=pal["ink"], width=2)
    draw.rectangle([bx0 - w * 0.012, col_bot, bx1 + w * 0.012,
                    col_bot + h * 0.06], fill=pal["gold"],
                   outline=pal["ink"], width=2)
    draw.rectangle([bx0 - w * 0.024, col_bot + h * 0.06, bx1 + w * 0.024, hy],
                   fill=card, outline=pal["ink"], width=2)
    brown = _blend(pal["gold"], pal["ink"], 0.35)
    draw.polygon(_rot_rect(hx, hyy, head_w, head_h, -38), fill=brown,
                 outline=pal["ink"])
    draw.polygon(_rot_rect(hx, hyy, head_w, head_h * 0.35, -38),
                 fill=pal["gold_light"])
    draw.line([hx, hyy, handle_to[0], handle_to[1]], fill=brown,
              width=max(4, int(h * 0.09)))
    draw.ellipse(list(block), fill=card, outline=pal["ink"], width=2)
    draw.rectangle(list(base), fill=pal["gold"], outline=pal["ink"], width=2)


def _scene_shanghai(draw, box, pal):
    # gap-01: Oriental Pearl Tower + magnifier (probe motif).
    # Sky navy (C8: no region-colour identity); magnifier gold.
    X, Y, w, h = _rel(box)
    x0, y0, x1, y1 = (float(v) for v in box)
    wide = w >= 5.0 * h
    hy = Y(0.80)
    draw.rectangle([x0, y0, x1, hy], fill=pal["navy"])
    draw.rectangle([x0, hy, x1, y1], fill=pal["navy_light"])
    draw.line([x0, hy, x1, hy], fill=pal["ink"], width=2)
    nl = pal["navy_light"]
    if wide:
        # varied skyline with two spires (distinct from Riyadh blocks)
        for fx0, fx1, top, col in ((0.01, 0.07, 0.45, nl),
                                   (0.08, 0.13, 0.30, pal["ink_soft"]),
                                   (0.14, 0.22, 0.52, nl),
                                   (0.23, 0.28, 0.36, pal["ink_soft"]),
                                   (0.29, 0.37, 0.48, nl),
                                   (0.38, 0.43, 0.33, pal["ink_soft"]),
                                   (0.44, 0.52, 0.50, nl),
                                   (0.53, 0.58, 0.40, pal["ink_soft"]),
                                   (0.59, 0.67, 0.54, nl),
                                   (0.68, 0.73, 0.44, pal["ink_soft"])):
            draw.rectangle([X(fx0), Y(top), X(fx1), hy], fill=col)
        for fx in (0.105, 0.405):  # spires
            draw.line([X(fx), Y(0.30), X(fx), Y(0.14)], fill=pal["card"],
                      width=2)
        px = X(0.86)
        pbase = Y(0.95)
        spheres = ((0.32, 0.15), (0.58, 0.19))
        mag_r = h * 0.24
    else:
        for fx0, fx1, top, col in ((0.01, 0.12, 0.48, nl),
                                   (0.13, 0.20, 0.34, pal["ink_soft"]),
                                   (0.21, 0.32, 0.54, nl),
                                   (0.33, 0.40, 0.42, pal["ink_soft"])):
            draw.rectangle([X(fx0), Y(top), X(fx1), hy], fill=col)
        draw.line([X(0.165), Y(0.34), X(0.165), Y(0.18)], fill=pal["card"],
                  width=2)
        px = X(0.68)
        pbase = Y(0.95)
        spheres = ((0.32, 0.14), (0.58, 0.18))
        mag_r = h * 0.23
    draw.polygon([(px - w * 0.035, pbase), (px, Y(0.52)),
                  (px + w * 0.035, pbase)], fill=nl, outline=pal["ink"],
                 width=2)
    draw.rectangle([px - w * 0.008, Y(0.28), px + w * 0.008, pbase],
                   fill=pal["card"])
    for fy, rr in spheres:
        cy = Y(fy)
        rpx = h * rr
        draw.ellipse([px - rpx, cy - rpx, px + rpx, cy + rpx],
                     fill=pal["gold_light"], outline=pal["ink"], width=2)
    draw.line([px, Y(spheres[0][0]) - h * spheres[0][1], px, Y(0.04)],
              fill=pal["card"], width=3)
    mx, my = px, Y(spheres[0][0])
    # white lens ring + handle so the magnifier reads against the
    # gold sphere on the navy sky (gold-on-gold muddied at 455x56)
    draw.ellipse([mx - mag_r, my - mag_r, mx + mag_r, my + mag_r],
                 outline=pal["white"], width=max(4, int(h * 0.07)))
    draw.line([mx + mag_r * 0.72, my + mag_r * 0.72,
               mx + mag_r * 1.35, my + mag_r * 1.35],
              fill=pal["white"], width=max(5, int(h * 0.09)))


# ---- feature scenes: strip icons (h <= 20) + tall versions ----

def _strip_bg(draw, box, pal, sky, ground=None, horizon=0.78):
    X, Y, w, h = _rel(box)
    x0, y0, x1, y1 = (float(v) for v in box)
    if ground is None:
        draw.rectangle([x0, y0, x1, y1], fill=sky)
        return Y(horizon)
    hy = Y(horizon)
    draw.rectangle([x0, y0, x1, hy], fill=sky)
    draw.rectangle([x0, hy, x1, y1], fill=ground)
    return hy


def _scene_chip_chart(draw, box, pal):
    # a6-02 Nvidia: chip + falling arrow (ink, no red per C8).
    X, Y, w, h = _rel(box)
    if h <= 20:
        _strip_bg(draw, box, pal, _tint(pal, pal["navy_light"], 0.45))
        s = h - 6
        cx0, cy0 = X(0.06), (h - s) / 2 + float(box[1])
        cx1, cy1 = cx0 + s, cy0 + s
        for i in range(3):
            t = 0.22 + i * 0.28
            draw.line([cx0 - 3, cy0 + s * t, cx0, cy0 + s * t],
                      fill=pal["ink_soft"], width=2)
            draw.line([cx1, cy0 + s * t, cx1 + 3, cy0 + s * t],
                      fill=pal["ink_soft"], width=2)
        draw.rectangle([cx0, cy0, cx1, cy1], fill=pal["navy"])
        draw.rectangle([cx0 + 2, cy0 + 2, cx1 - 2, cy1 - 2],
                       fill=_tint(pal, pal["navy_light"], 0.25))
        pts = [(X(0.30), Y(0.22)), (X(0.48), Y(0.42)), (X(0.60), Y(0.32)),
               (X(0.78), Y(0.58)), (X(0.94), Y(0.74))]
        draw.line(pts, fill=pal["ink"], width=2, joint="curve")
        ex, ey = pts[-1]
        draw.polygon([(ex, ey), (ex - 7, ey - 1), (ex - 2, ey - 6)],
                     fill=pal["ink"])
        return
    draw.rectangle(box, fill=_tint(pal, pal["navy_light"], 0.40))
    for fy in (0.30, 0.55, 0.80):
        draw.line([X(0.34), Y(fy), X(0.97), Y(fy)], fill=pal["card_edge"],
                  width=1)
    # v3 port box (172x30): red chip overlays bottom-left (y 6..26,
    # x to ~139); focal chip icon moves right, arrow rides the top strip.
    port = 28 <= h <= 32
    if port:
        cx0, cy0, cx1, cy1 = X(0.82), Y(0.14), X(0.95), Y(0.86)
    else:
        cx0, cy0, cx1, cy1 = X(0.05), Y(0.20), X(0.29), Y(0.80)
    pin = pal["ink_soft"]
    for i in range(4):
        t = 0.18 + i * 0.21
        py = cy0 + (cy1 - cy0) * t
        if port:
            draw.line([cx0 - 3, py, cx0, py], fill=pin, width=2)
            draw.line([cx1, py, cx1 + 3, py], fill=pin, width=2)
        else:
            draw.line([X(0.02), py, cx0, py], fill=pin, width=2)
            draw.line([cx1, py, X(0.32), py], fill=pin, width=2)
    draw.rectangle([cx0, cy0, cx1, cy1], fill=pal["navy"])
    draw.rectangle([cx0 + 4, cy0 + 4, cx1 - 4, cy1 - 4],
                   fill=_tint(pal, pal["navy_light"], 0.25))
    if port:
        # falling arrow along the top strip (above the chip zone),
        # ending at the icon's top-left corner
        pts = [(X(0.04), Y(0.09)), (X(0.30), Y(0.14)), (X(0.48), Y(0.08)),
               (X(0.66), Y(0.14)), (X(0.79), Y(0.17))]
        draw.line(pts, fill=pal["ink"], width=2, joint="curve")
        ex, ey = pts[-1]
        draw.polygon([(ex, ey), (ex - 6, ey - 1), (ex - 2, ey - 5)],
                     fill=pal["ink"])
        return
    pts = [(X(0.38), Y(0.22)), (X(0.52), Y(0.40)), (X(0.62), Y(0.30)),
           (X(0.76), Y(0.58)), (X(0.92), Y(0.76))]
    draw.line(pts, fill=pal["ink"], width=3, joint="curve")
    ex, ey = pts[-1]
    draw.polygon([(ex, ey), (ex - w * 0.07, ey - h * 0.02),
                  (ex - w * 0.02, ey - h * 0.24)], fill=pal["ink"])


def _scene_vessel(draw, box, pal):
    # a5-03 Myanmar: vessel silhouette on water.
    X, Y, w, h = _rel(box)
    sky = _tint(pal, pal["navy_light"], 0.45)
    sea = _tint(pal, pal["navy_light"], 0.20)
    if h <= 20:
        sea_y = _strip_bg(draw, box, pal, sky, sea, 0.66)
        hx0, hx1 = X(0.08), X(0.62)
        draw.polygon([(hx0, sea_y), (hx1, sea_y),
                      (hx1 - w * 0.05, sea_y + h * 0.24),
                      (hx0 + w * 0.04, sea_y + h * 0.24)], fill=pal["navy"])
        draw.rectangle([X(0.22), sea_y - h * 0.30, X(0.42), sea_y],
                       fill=pal["card"], outline=pal["navy"], width=1)
        draw.line([X(0.50), sea_y, X(0.50), sea_y - h * 0.42],
                  fill=pal["ink_soft"], width=2)
        draw.polygon([(X(0.50), sea_y - h * 0.42), (X(0.50), sea_y - h * 0.26),
                      (X(0.57), sea_y - h * 0.34)], fill=pal["gold"])
        _plane(draw, X(0.84), Y(0.24), w * 0.08, pal["navy"])
        return
    sea_y = _sky(draw, box, pal, sky, sea, 0.64)
    # v3 port box (172x30): vessel focal shifts right of the chip zone.
    port = 28 <= h <= 32
    if port:
        hx0, hx1 = X(0.54), X(0.96)
        cab = (X(0.64), X(0.82))
        mast_x, flag_x = X(0.88), X(0.94)
        plane_xy, plane_s = (X(0.30), Y(0.16)), w * 0.07
        path = [(X(0.38), Y(0.22)), (X(0.48), Y(0.30)), (X(0.56), Y(0.26))]
    else:
        hx0, hx1 = X(0.10), X(0.52)
        cab = (X(0.20), X(0.38))
        mast_x, flag_x = X(0.44), X(0.50)
        plane_xy, plane_s = (X(0.80), Y(0.20)), w * 0.09
        path = [(X(0.70), Y(0.26)), (X(0.58), Y(0.36)), (X(0.48), Y(0.30))]
    draw.polygon([(hx0, sea_y), (hx1, sea_y), (hx1 - w * 0.05, sea_y + h * 0.22),
                  (hx0 + w * 0.04, sea_y + h * 0.22)], fill=pal["navy"])
    draw.rectangle([cab[0], sea_y - h * 0.26, cab[1], sea_y],
                   fill=pal["card"], outline=pal["navy"], width=1)
    draw.line([mast_x, sea_y, mast_x, sea_y - h * 0.34], fill=pal["ink_soft"],
              width=2)
    draw.polygon([(mast_x, sea_y - h * 0.34), (mast_x, sea_y - h * 0.20),
                  (flag_x, sea_y - h * 0.27)], fill=pal["gold"])
    _plane(draw, plane_xy[0], plane_xy[1], plane_s, pal["navy"])
    _dotted(draw, path, pal["navy_light"], r=1.1, step=4.5)
    for fx in (0.60, 0.72, 0.84, 0.93):
        draw.line([X(fx), Y(0.84), X(fx) + w * 0.05, Y(0.84)],
                  fill=_tint(pal, pal["navy_light"], 0.15), width=2)


def _scene_port(draw, box, pal):
    # a5-01 China pause: container stack + crane.
    X, Y, w, h = _rel(box)
    sky = _tint(pal, pal["navy_light"], 0.45)
    gnd = _tint(pal, pal["gold"], 0.40)
    cols = [pal["navy"], pal["navy_light"], pal["gold"], pal["grey"]]
    if h <= 20:
        gy = _strip_bg(draw, box, pal, sky, gnd, 0.84)
        bw, bh = w * 0.16, h * 0.30
        for si, (fx, n) in enumerate(((0.04, 2), (0.22, 1))):
            for i in range(n):
                y1 = gy - i * (bh + 1)
                draw.rectangle([X(fx), y1 - bh, X(fx) + bw, y1],
                               fill=cols[(si + i) % len(cols)],
                               outline=pal["ink_soft"], width=1)
        mx = X(0.58)
        draw.line([mx, gy, mx, Y(0.14)], fill=pal["ink_soft"], width=2)
        draw.line([mx, Y(0.14), X(0.96), Y(0.14)], fill=pal["ink_soft"],
                  width=2)
        hx = X(0.84)
        draw.line([hx, Y(0.14), hx, Y(0.44)], fill=pal["ink_soft"], width=1)
        draw.rectangle([hx - bw / 2, Y(0.44), hx + bw / 2, Y(0.44) + bh],
                       fill=pal["navy"], outline=pal["ink_soft"], width=1)
        return
    gy = _sky(draw, box, pal, sky, gnd, 0.84)
    # v3 port box (172x30): stacks + crane focal shift right of chip zone.
    port = 28 <= h <= 32
    if port:
        stacks = [(0.56, 1), (0.72, 1)]
        mx, jib_x0, brace_x, hx = X(0.90), X(0.56), X(0.78), X(0.66)
    else:
        stacks = [(0.04, 3), (0.20, 2), (0.36, 3)]
        mx, jib_x0, brace_x, hx = X(0.66), None, X(0.56), X(0.86)
    bw, bh = w * 0.145, h * 0.20
    for si, (fx, n) in enumerate(stacks):
        for i in range(n):
            y1 = gy - i * (bh + 1.5)
            draw.rectangle([X(fx), y1 - bh, X(fx) + bw, y1],
                           fill=cols[(si + i) % len(cols)],
                           outline=_tint(pal, pal["ink"], 0.55), width=1)
    draw.line([mx, gy, mx, Y(0.10)], fill=pal["ink_soft"], width=3)
    if port:
        draw.line([jib_x0, Y(0.10), X(0.97), Y(0.10)], fill=pal["ink_soft"],
                  width=3)
        draw.line([mx, Y(0.10), brace_x, Y(0.30)], fill=pal["ink_soft"],
                  width=1)
    else:
        draw.line([mx, Y(0.10), X(0.97), Y(0.10)], fill=pal["ink_soft"],
                  width=3)
        draw.line([mx, Y(0.10), brace_x, Y(0.30)], fill=pal["ink_soft"],
                  width=1)
    draw.line([hx, Y(0.10), hx, Y(0.42)], fill=pal["ink_soft"], width=1)
    draw.rectangle([hx - bw / 2, Y(0.42), hx + bw / 2, Y(0.42) + bh],
                   fill=pal["navy"], outline=_tint(pal, pal["ink"], 0.55),
                   width=1)


def _scene_podium(draw, box, pal):
    # a4-03 Iran: podium + conditions list.
    X, Y, w, h = _rel(box)
    bg = _tint(pal, pal["navy_light"], 0.45)
    if h <= 20:
        gy = _strip_bg(draw, box, pal, bg, None, 0.88)
        px0, px1 = X(0.08), X(0.30)
        draw.polygon([(px0, Y(0.40)), (px1, Y(0.40)),
                      (px1 - w * 0.02, gy), (px0 + w * 0.02, gy)],
                     fill=pal["navy"])
        draw.rectangle([px0 - w * 0.015, Y(0.30), px1 + w * 0.015, Y(0.40)],
                       fill=pal["navy_light"])
        draw.line([X(0.19), Y(0.30), X(0.19), Y(0.16)], fill=pal["ink_soft"],
                  width=2)
        r = h * 0.09
        draw.ellipse([X(0.19) - r, Y(0.16) - r, X(0.19) + r, Y(0.16) + r],
                     fill=pal["ink_soft"])
        lx0, lx1, ly0, ly1 = X(0.42), X(0.96), Y(0.14), Y(0.86)
        draw.rectangle([lx0, ly0, lx1, ly1], fill=pal["card"],
                       outline=pal["card_edge"], width=1)
        for i in range(3):
            yy = ly0 + (ly1 - ly0) * (0.22 + i * 0.28)
            draw.ellipse([lx0 + 3, yy - 1.2, lx0 + 5.4, yy + 1.2],
                         fill=pal["gold"])
            draw.line([lx0 + 8, yy, lx1 - 4 - (i % 2) * w * 0.08, yy],
                      fill=pal["ink_soft"], width=1)
        return
    draw.rectangle(box, fill=bg)
    gy = Y(0.88)
    draw.line([X(0.02), gy, X(0.98), gy], fill=pal["card_edge"], width=1)
    # v3 port box (168x30): podium focal shifts right of the chip zone;
    # conditions list narrows and moves right with it.
    port = 28 <= h <= 32
    if port:
        px0, px1 = X(0.76), X(0.96)
        inset = (X(0.83), X(0.89))
        mic_x = X(0.86)
        lx0, lx1 = X(0.52), X(0.72)
        n_lines, line_step = 4, 0.20
    else:
        px0, px1 = X(0.10), X(0.40)
        inset = (X(0.20), X(0.30))
        mic_x = X(0.25)
        lx0, lx1 = X(0.56), X(0.96)
        n_lines, line_step = 7, 0.12
    draw.polygon([(px0, Y(0.38)), (px1, Y(0.38)), (px1 - w * 0.03, gy),
                  (px0 + w * 0.03, gy)], fill=pal["navy"])
    draw.rectangle([px0 - w * 0.02, Y(0.30), px1 + w * 0.02, Y(0.38)],
                   fill=pal["navy_light"])
    draw.rectangle([inset[0], Y(0.52), inset[1], Y(0.66)], fill=pal["gold"])
    draw.line([mic_x, Y(0.30), mic_x, Y(0.14)], fill=pal["ink_soft"],
              width=2)
    r = h * 0.07
    draw.ellipse([mic_x - r, Y(0.14) - r, mic_x + r, Y(0.14) + r],
                 fill=pal["ink_soft"])
    ly0, ly1 = Y(0.14), Y(0.84)
    draw.rectangle([lx0, ly0, lx1, ly1], fill=pal["card"],
                   outline=pal["card_edge"], width=1)
    for i in range(n_lines):
        yy = ly0 + (ly1 - ly0) * (0.14 + i * line_step)
        draw.ellipse([lx0 + 3, yy - 1.2, lx0 + 5.4, yy + 1.2], fill=pal["gold"])
        draw.line([lx0 + 8, yy, lx1 - 4 - (i % 3) * w * 0.05, yy],
                  fill=pal["ink_soft"], width=1)


def _scene_gaza(draw, box, pal):
    # a4-05 Gaza: strike burst over rooftops (generic, no people).
    X, Y, w, h = _rel(box)
    sky = _tint(pal, pal["grey"], 0.40)
    gnd = _tint(pal, pal["gold"], 0.35)
    if h <= 20:
        gy = _strip_bg(draw, box, pal, sky, gnd, 0.84)
        for fx0, fx1, top, col in ((0.01, 0.16, 0.52, pal["navy"]),
                                   (0.18, 0.30, 0.40, pal["navy_light"]),
                                   (0.62, 0.74, 0.46, pal["navy"]),
                                   (0.76, 0.88, 0.56, pal["navy_light"]),
                                   (0.90, 0.99, 0.44, pal["navy"])):
            draw.rectangle([X(fx0), Y(top), X(fx1), gy], fill=col)
        sx0, sx1 = X(0.38), X(0.56)
        draw.rectangle([sx0, Y(0.50), sx1, gy], fill=_tint(pal, pal["grey"], 0.15))
        draw.polygon([(sx0, Y(0.50)), (X(0.47), Y(0.60)), (sx1, Y(0.50))],
                     fill=_tint(pal, pal["grey"], 0.15))
        _burst(draw, X(0.47), Y(0.46), h * 0.30, pal)
        return
    gy = _sky(draw, box, pal, sky, gnd, 0.82)
    mid = _tint(pal, pal["navy"], 0.35)
    # v3 port box (172x30): struck building + burst shift right of the
    # chip zone (chip ends x~78); burst enlarged for legibility.
    port = 28 <= h <= 32
    if port:
        blocks = [(0.01, 0.12, 0.55, mid), (0.13, 0.22, 0.44, pal["navy_light"]),
                  (0.23, 0.33, 0.62, _tint(pal, pal["grey"], 0.25)),
                  (0.60, 0.70, 0.50, mid), (0.71, 0.79, 0.60, pal["navy_light"]),
                  (0.80, 0.89, 0.46, _tint(pal, pal["grey"], 0.25)),
                  (0.90, 0.99, 0.58, mid)]
        sx0, sx1, bcx, burst_r = X(0.44), X(0.57), 0.505, h * 0.16
        smoke_pts = ((0.505, 0.42, 0.10), (0.52, 0.30, 0.13),
                     (0.54, 0.18, 0.16))
    else:
        blocks = [(0.01, 0.12, 0.55, mid), (0.13, 0.22, 0.44, pal["navy_light"]),
                  (0.23, 0.33, 0.62, _tint(pal, pal["grey"], 0.25)),
                  (0.56, 0.66, 0.50, mid), (0.67, 0.77, 0.60, pal["navy_light"]),
                  (0.78, 0.88, 0.46, _tint(pal, pal["grey"], 0.25)),
                  (0.89, 0.99, 0.58, mid)]
        sx0, sx1, bcx, burst_r = X(0.40), X(0.53), 0.465, h * 0.12
        smoke_pts = ((0.465, 0.42, 0.10), (0.48, 0.30, 0.13),
                     (0.50, 0.18, 0.16))
    for fx0, fx1, top, col in blocks:
        draw.rectangle([X(fx0), Y(top), X(fx1), gy], fill=col)
    draw.rectangle([sx0, Y(0.52), sx1, gy], fill=_tint(pal, pal["grey"], 0.15))
    draw.polygon([(sx0, Y(0.52)), (X(bcx), Y(0.60)), (sx1, Y(0.52))],
                 fill=_tint(pal, pal["grey"], 0.15))
    smoke = _tint(pal, pal["grey"], 0.45)
    for fx, fy, rr in smoke_pts:
        cx, cy, rpx = X(fx), Y(fy), h * rr
        draw.ellipse([cx - rpx, cy - rpx * 0.8, cx + rpx, cy + rpx * 0.8],
                     fill=smoke)
    _burst(draw, X(bcx), Y(0.50), burst_r, pal)
    _plane(draw, X(0.84), Y(0.16), w * 0.07, pal["ink_soft"])


def _scene_vial(draw, box, pal):
    # a6-07 Gavi: vaccine vial.
    X, Y, w, h = _rel(box)
    bg = _tint(pal, pal["navy_light"], 0.50)
    if h <= 20:
        gy = _strip_bg(draw, box, pal, bg, None, 0.90)
        vx0, vx1 = X(0.10), X(0.30)
        draw.rounded_rectangle([vx0, Y(0.34), vx1, gy], radius=3,
                               fill=pal["card"], outline=pal["navy"], width=2)
        draw.rectangle([vx0 + 1, Y(0.16), vx1 - 1, Y(0.34)], fill=pal["gold"])
        draw.rectangle([vx0 + 2, Y(0.56), vx1 - 2, Y(0.78)],
                       fill=_tint(pal, pal["navy_light"], 0.30))
        # syringe diagonal right
        sx, sy = X(0.58), Y(0.58)
        draw.polygon(_rot_rect(sx, sy, w * 0.36, h * 0.26, -24),
                     fill=pal["card"], outline=pal["navy"])
        a = math.radians(-24)
        nx = sx + math.cos(a) * w * 0.18
        ny = sy + math.sin(a) * w * 0.18
        draw.line([nx, ny, nx + w * 0.14, ny - h * 0.16], fill=pal["ink_soft"],
                  width=2)
        return
    draw.rectangle(box, fill=bg)
    gy = Y(0.88)
    draw.line([X(0.02), gy, X(0.98), gy],
              fill=_tint(pal, pal["navy_light"], 0.45), width=1)
    # v3 port box (172x30): vial focal shifts right of the chip zone.
    port = 28 <= h <= 32
    vx0, vx1 = (X(0.68), X(0.88)) if port else (X(0.16), X(0.38))
    draw.rounded_rectangle([vx0, Y(0.30), vx1, gy], radius=4,
                           fill=pal["card"], outline=pal["navy"], width=2)
    draw.rectangle([vx0 + 2, Y(0.16), vx1 - 2, Y(0.30)], fill=pal["gold"])
    draw.rectangle([vx0 + 2, Y(0.52), vx1 - 2, Y(0.74)],
                   fill=_tint(pal, pal["navy_light"], 0.30))
    dx, dy = (vx0 + vx1) / 2, Y(0.63)
    dr = h * 0.09
    draw.polygon([(dx, dy - dr * 1.5), (dx - dr, dy + dr * 0.4),
                  (dx + dr, dy + dr * 0.4)], fill=pal["card"])
    draw.ellipse([dx - dr, dy - dr * 0.2, dx + dr, dy + dr * 1.1],
                 fill=pal["card"])
    sx, sy = (X(0.50), Y(0.62)) if port else (X(0.56), Y(0.66))
    draw.polygon(_rot_rect(sx, sy, w * 0.34, h * 0.20, -32), fill=pal["card"],
                 outline=pal["navy"])
    a = math.radians(-32)
    nx = sx + math.cos(a) * w * 0.17
    ny = sy + math.sin(a) * w * 0.17
    draw.line([nx, ny, nx + w * 0.13, ny - h * 0.20], fill=pal["ink_soft"],
              width=2)
    px = sx - math.cos(a) * w * 0.17
    py = sy - math.sin(a) * w * 0.17
    draw.line([px, py, px - w * 0.07, py + h * 0.10], fill=pal["ink_soft"],
              width=3)
    _star4(draw, X(0.94) if port else X(0.90), Y(0.16) if port else Y(0.22),
           h * 0.10, _tint(pal, pal["navy_light"], 0.20))


def _scene_trophy(draw, box, pal):
    X, Y, w, h = _rel(box)
    draw.rectangle(box, fill=_tint(pal, pal["gold_light"], 0.40))
    gy = Y(0.90)
    cx = X(0.50)
    gold, gl = pal["gold"], pal["gold_light"]
    hw = w * 0.16
    draw.arc([cx - hw - w * 0.09, Y(0.20), cx - hw + w * 0.10, Y(0.52)],
             start=90, end=270, fill=gold, width=3)
    draw.arc([cx + hw - w * 0.10, Y(0.20), cx + hw + w * 0.09, Y(0.52)],
             start=270, end=90, fill=gold, width=3)
    draw.polygon([(cx - hw, Y(0.14)), (cx + hw, Y(0.14)),
                  (cx + hw * 0.55, Y(0.58)), (cx - hw * 0.55, Y(0.58))],
                 fill=gold)
    draw.rectangle([cx - hw, Y(0.14), cx + hw, Y(0.22)], fill=gl)
    draw.polygon([(cx - hw * 0.55, Y(0.58)), (cx + hw * 0.55, Y(0.58)),
                  (cx + hw * 0.30, Y(0.66)), (cx - hw * 0.30, Y(0.66))],
                 fill=gold)
    draw.rectangle([cx - w * 0.03, Y(0.66), cx + w * 0.03, Y(0.78)], fill=gold)
    draw.rectangle([cx - w * 0.11, Y(0.78), cx + w * 0.11, gy], fill=pal["navy"])
    _star4(draw, X(0.16), Y(0.26), h * 0.11, gl)
    _star4(draw, X(0.84), Y(0.26), h * 0.11, gl)
    _star4(draw, X(0.78), Y(0.58), h * 0.08, _tint(pal, gold, 0.25))


def _scene_pharma(draw, box, pal):
    # gap-02 Sanofi: capsule (navy/card two-tone, no red).
    X, Y, w, h = _rel(box)
    bg = _tint(pal, pal["navy_light"], 0.45)
    if h <= 20:
        gy = _strip_bg(draw, box, pal, bg, None, 0.88)
        cx0, cy0, cx1, cy1 = X(0.06), Y(0.24), X(0.52), Y(0.76)
        rad = (cy1 - cy0) / 2
        draw.rounded_rectangle([cx0, cy0, cx1, cy1], radius=rad,
                               fill=pal["card"], outline=pal["navy"], width=2)
        draw.rounded_rectangle([cx0, cy0, (cx0 + cx1) / 2, cy1], radius=rad,
                               fill=pal["navy"])
        draw.rectangle([(cx0 + cx1) / 2 - rad * 0.4, cy0 + 1,
                        (cx0 + cx1) / 2, cy1 - 1], fill=pal["navy"])
        vx0, vx1 = X(0.62), X(0.76)
        draw.rounded_rectangle([vx0, Y(0.40), vx1, gy], radius=3,
                               fill=pal["card"], outline=pal["navy"], width=2)
        draw.rectangle([vx0 + 1, Y(0.24), vx1 - 1, Y(0.40)],
                       fill=pal["navy_light"])
        bx, by, br = X(0.88), Y(0.50), h * 0.34
        draw.ellipse([bx - br, by - br, bx + br, by + br], fill=pal["card"],
                     outline=pal["navy"], width=2)
        draw.rectangle([bx - br * 0.20, by - br * 0.60, bx + br * 0.20,
                        by + br * 0.60], fill=pal["navy"])
        draw.rectangle([bx - br * 0.60, by - br * 0.20, bx + br * 0.60,
                        by + br * 0.20], fill=pal["navy"])
        return
    draw.rectangle(box, fill=bg)
    gy = Y(0.88)
    draw.line([X(0.02), gy, X(0.98), gy], fill=pal["card_edge"], width=1)
    ex = X(0.18)
    draw.polygon([(ex - w * 0.09, gy), (ex - w * 0.012, Y(0.12)),
                  (ex + w * 0.012, Y(0.12)), (ex + w * 0.09, gy)],
                 fill=pal["navy"])
    draw.rectangle([ex - w * 0.055, Y(0.42), ex + w * 0.055, Y(0.48)],
                   fill=pal["navy"])
    draw.rectangle([ex - w * 0.075, Y(0.64), ex + w * 0.075, Y(0.70)],
                   fill=pal["navy"])
    draw.polygon([(ex - w * 0.045, gy), (ex, Y(0.70)), (ex + w * 0.045, gy)],
                 fill=bg)
    draw.line([ex, Y(0.12), ex, Y(0.05)], fill=pal["navy"], width=2)
    # v3 port box (172x30): capsule focal shifts right of the chip zone
    # (chip ends x~110); vial + cross badge move right with it.
    port = 28 <= h <= 32
    if port:
        cx0, cy0, cx1, cy1 = X(0.64), Y(0.34), X(0.88), Y(0.66)
    else:
        cx0, cy0, cx1, cy1 = X(0.42), Y(0.34), X(0.78), Y(0.66)
    rad = (cy1 - cy0) / 2
    draw.rounded_rectangle([cx0, cy0, cx1, cy1], radius=rad, fill=pal["card"],
                           outline=pal["navy"], width=2)
    draw.rounded_rectangle([cx0, cy0, (cx0 + cx1) / 2, cy1], radius=rad,
                           fill=pal["navy"])
    draw.rectangle([(cx0 + cx1) / 2 - rad * 0.4, cy0 + 1, (cx0 + cx1) / 2, cy1 - 1],
                   fill=pal["navy"])
    vx0, vx1 = (X(0.90), X(0.98)) if port else (X(0.84), X(0.94))
    draw.rounded_rectangle([vx0, Y(0.44), vx1, gy], radius=3, fill=pal["card"],
                           outline=pal["navy"], width=2)
    draw.rectangle([vx0 + 1, Y(0.34), vx1 - 1, Y(0.44)], fill=pal["navy_light"])
    bx, by, br = (X(0.76) if port else X(0.60)), Y(0.19), h * 0.17
    draw.ellipse([bx - br, by - br, bx + br, by + br], fill=pal["card"],
                 outline=pal["navy"], width=2)
    draw.rectangle([bx - br * 0.20, by - br * 0.62, bx + br * 0.20, by + br * 0.62],
                   fill=pal["navy"])
    draw.rectangle([bx - br * 0.62, by - br * 0.20, bx + br * 0.62, by + br * 0.20],
                   fill=pal["navy"])


def _scene_station(draw, box, pal):
    # a6-06 Shenzhou: rocket (strip: horizontal; tall: vertical + Earth).
    X, Y, w, h = _rel(box)
    if h <= 20:
        _strip_bg(draw, box, pal, _tint(pal, pal["navy"], 0.30))
        for fx, fy in ((0.06, 0.25), (0.16, 0.70), (0.86, 0.20), (0.94, 0.65)):
            draw.ellipse([X(fx) - 1, Y(fy) - 1, X(fx) + 1, Y(fy) + 1],
                         fill=pal["card"])
        cy = Y(0.50)
        rh = h * 0.30
        # flame
        draw.polygon([(X(0.10), cy), (X(0.24), cy - rh * 0.7),
                      (X(0.24), cy + rh * 0.7)], fill=pal["gold"])
        draw.polygon([(X(0.16), cy), (X(0.24), cy - rh * 0.4),
                      (X(0.24), cy + rh * 0.4)], fill=pal["gold_light"])
        # body + nose
        draw.rectangle([X(0.24), cy - rh, X(0.68), cy + rh], fill=pal["card"],
                       outline=pal["navy"], width=1)
        draw.polygon([(X(0.68), cy - rh), (X(0.82), cy), (X(0.68), cy + rh)],
                     fill=pal["navy"])
        # fins
        draw.polygon([(X(0.24), cy - rh), (X(0.32), cy - rh),
                      (X(0.24), cy - rh * 2.0)], fill=pal["gold"])
        draw.polygon([(X(0.24), cy + rh), (X(0.32), cy + rh),
                      (X(0.24), cy + rh * 2.0)], fill=pal["gold"])
        # window
        r = rh * 0.45
        draw.ellipse([X(0.56) - r, cy - r, X(0.56) + r, cy + r],
                     fill=pal["navy_light"])
        return
    draw.rectangle(box, fill=_tint(pal, pal["navy"], 0.30))
    for fx, fy in ((0.06, 0.16), (0.16, 0.42), (0.30, 0.10), (0.44, 0.26),
                   (0.58, 0.12), (0.70, 0.40), (0.82, 0.14), (0.93, 0.32),
                   (0.10, 0.62), (0.88, 0.60)):
        draw.ellipse([X(fx) - 1, Y(fy) - 1, X(fx) + 1, Y(fy) + 1],
                     fill=pal["card"])
    er = w * 0.90
    ecx, ecy = X(0.50), Y(0.84) + er
    draw.ellipse([ecx - er, ecy - er, ecx + er, ecy + er],
                 fill=_tint(pal, pal["navy_light"], 0.30))
    # vertical rocket; v3 port box (168x30): focal shifts right of chip zone
    cx = X(0.80) if 28 <= h <= 32 else X(0.50)
    rw = w * 0.07
    draw.polygon([(cx - rw, Y(0.62)), (cx + rw, Y(0.62)), (cx, Y(0.82))],
                 fill=pal["gold"])
    draw.polygon([(cx - rw * 0.6, Y(0.62)), (cx + rw * 0.6, Y(0.62)),
                  (cx, Y(0.76))], fill=pal["gold_light"])
    draw.rectangle([cx - rw, Y(0.26), cx + rw, Y(0.62)], fill=pal["card"],
                   outline=pal["navy"], width=1)
    draw.polygon([(cx - rw, Y(0.26)), (cx + rw, Y(0.26)), (cx, Y(0.08))],
                 fill=pal["navy"])
    draw.polygon([(cx - rw, Y(0.48)), (cx - rw, Y(0.62)),
                  (cx - rw * 2.2, Y(0.62))], fill=pal["gold"])
    draw.polygon([(cx + rw, Y(0.48)), (cx + rw, Y(0.62)),
                  (cx + rw * 2.2, Y(0.62))], fill=pal["gold"])
    r = rw * 0.45
    draw.ellipse([cx - r, Y(0.38) - r, cx + r, Y(0.38) + r],
                 fill=pal["navy_light"])


def _scene_zaporizhzhia(draw, box, pal):
    """gap-04 Zaporizhzhia: damaged building + burst (gold/white)."""
    X, Y, w, h = _rel(box)
    x0, y0, x1, y1 = (float(v) for v in box)
    if h <= 20:
        hy = _strip_bg(draw, box, pal, _tint(pal, pal["navy_light"], 0.40),
                       _tint(pal, pal["gold"], 0.40), 0.84)
        for fx0, fx1, top, col in ((0.01, 0.14, 0.52, pal["navy"]),
                                   (0.16, 0.26, 0.40, pal["navy_light"]),
                                   (0.66, 0.78, 0.48, pal["navy"]),
                                   (0.80, 0.92, 0.58, pal["navy_light"]),
                                   (0.94, 0.99, 0.44, pal["navy"])):
            draw.rectangle([X(fx0), Y(top), X(fx1), hy], fill=col)
        bx0, bx1 = X(0.36), X(0.56)
        draw.rectangle([bx0, Y(0.36), bx1, hy],
                       fill=_tint(pal, pal["grey"], 0.20))
        draw.polygon([(bx0, Y(0.36)), (X(0.46), Y(0.50)), (bx1, Y(0.36))],
                     fill=_tint(pal, pal["grey"], 0.20))
        _burst(draw, X(0.46), Y(0.34), h * 0.32, pal)
        return
    hy = Y(0.80)
    draw.rectangle([x0, y0, x1, Y(0.45)],
                   fill=_tint(pal, pal["navy_light"], 0.40))
    draw.rectangle([x0, Y(0.45), x1, hy],
                   fill=_tint(pal, pal["gold_light"], 0.25))
    draw.rectangle([x0, hy, x1, y1], fill=_tint(pal, pal["gold"], 0.40))
    draw.line([x0, hy, x1, hy],
              fill=_blend(_tint(pal, pal["gold"], 0.40), pal["ink"], 0.25),
              width=1)
    sx, sr = X(0.90), h * 0.34
    draw.ellipse([sx - sr, hy - sr, sx + sr, hy + sr],
                 fill=pal["gold_light"], outline=pal["gold"], width=1)
    navy, nl = pal["navy"], pal["navy_light"]
    mid = _tint(pal, navy, 0.30)
    # v3 port box (172x30): damaged building + burst shift right of the
    # chip zone (chip ends x~107; unshifted building edge had 0.3px margin).
    port = 28 <= h <= 32
    if port:
        blocks = [(0.01, 0.10, 0.62, mid), (0.11, 0.19, 0.52, navy),
                  (0.20, 0.28, 0.66, nl), (0.29, 0.37, 0.56, mid),
                  (0.38, 0.46, 0.64, navy), (0.47, 0.55, 0.54, nl),
                  (0.80, 0.87, 0.58, navy), (0.88, 0.94, 0.48, mid),
                  (0.95, 0.99, 0.62, nl)]
        wins = ((0.83, 0.66), (0.90, 0.58), (0.96, 0.70), (0.50, 0.62))
        bx0, bx1, bcx = X(0.66), X(0.77), 0.715
        smoke_pts = ((0.715, 0.34, 0.11), (0.73, 0.22, 0.14),
                     (0.745, 0.11, 0.17))
    else:
        blocks = [(0.01, 0.10, 0.62, mid), (0.11, 0.19, 0.52, navy),
                  (0.20, 0.28, 0.66, nl), (0.29, 0.37, 0.56, mid),
                  (0.38, 0.46, 0.64, navy), (0.47, 0.55, 0.54, nl),
                  (0.74, 0.82, 0.58, navy), (0.83, 0.90, 0.48, mid),
                  (0.91, 0.99, 0.62, nl)]
        wins = ((0.77, 0.66), (0.86, 0.58), (0.95, 0.70), (0.50, 0.62))
        bx0, bx1, bcx = X(0.62), X(0.73), 0.675
        smoke_pts = ((0.675, 0.34, 0.11), (0.69, 0.22, 0.14),
                     (0.705, 0.11, 0.17))
    for fx0, fx1, top, col in blocks:
        draw.rectangle([X(fx0), Y(top), X(fx1), hy], fill=col)
    win = _tint(pal, pal["gold_light"], 0.20)
    for fx, fy in wins:
        draw.rectangle([X(fx), Y(fy), X(fx) + 2, Y(fy) + 2], fill=win)
    draw.rectangle([bx0, Y(0.44), bx1, hy],
                   fill=_tint(pal, pal["grey"], 0.20))
    draw.polygon([(bx0, Y(0.44)), (X(bcx), Y(0.53)), (bx1, Y(0.44))],
                 fill=_tint(pal, pal["grey"], 0.20))
    smoke = _tint(pal, pal["grey"], 0.40)
    for fx, fy, rr in smoke_pts:
        cx, cy, rpx = X(fx), Y(fy), h * rr
        draw.ellipse([cx - rpx, cy - rpx * 0.8, cx + rpx, cy + rpx * 0.8],
                     fill=smoke)
    _burst(draw, X(bcx), Y(0.42), h * 0.18, pal)


_SCENES = {
    "a4-01": _scene_riyadh,
    "a6-04": _scene_courthouse,
    "gap-01": _scene_shanghai,
    "a6-02": _scene_chip_chart,
    "a5-03": _scene_vessel,
    "a5-01": _scene_port,
    "a4-03": _scene_podium,
    "a4-05": _scene_gaza,
    "a6-07": _scene_vial,
    "a6-08": _scene_trophy,
    "gap-02": _scene_pharma,
    "a6-06": _scene_station,
    "gap-04": _scene_zaporizhzhia,
    # a6-01: markets table card — intentionally no scene.
}


def draw_scene(draw, box, story_id, palette):
    """Draw the flat scene for story_id inside box=(x0, y0, x1, y1).

    Returns True if drawn; False for a6-01 (markets table, no scene)
    and unknown story ids. Scenes contain no text. v2: badges sit
    outside illustrations, so the full box is usable. v3 port: chips
    overlay bottom-left; feature focals at 172x30/168x30 are shifted
    clear of the chip zone (see per-scene port branches).
    """
    fn = _SCENES.get(story_id)
    if fn is None:
        return False
    pal = _pal(palette)
    _clipped(draw, box, lambda d, b: fn(d, b, pal))
    return True


# ---------------------------------------------------------------- world map

# Natural Earth 110m land (public domain, naturalearthdata.com),
# fetched 2026-11-25 from nvkelso/natural-earth-vector
# (geojson/ne_110m_land.geojson), simplified offline with
# Douglas-Peucker (tolerance 0.5 deg), coordinates rounded to 0.1 deg,
# outer rings only, rings < 1.2 deg^2 dropped, Antarctica dropped.
# 66 rings / 1345 points / ~17 KB embedded. Equirectangular via
# _project; lat window 85/-65 matches the 284x118 map box aspect.
_LAND = [((-67.8,-53.9),(-65,-54.7),(-69.2,-55.5),(-74.7,-52.8),(-71.1,-54.1),(-70.3,-52.9),(-68.6,-52.6),(-67.8,-53.9)),((-58.5,-51.1),(-58,-51.9),(-61.2,-51.9),(-58.5,-51.1)),((70.3,-49.7),(68.7,-49.8),(68.9,-48.6),(70.5,-49.1),(70.3,-49.7)),((145.4,-40.8),(148.3,-40.9),(147.9,-43.2),(146,-43.5),(144.7,-41.2),(145.4,-40.8)),((173,-40.9),(174.2,-41.3),(172.7,-43.4),(173.1,-43.9),(171.5,-44.2),(169.3,-46.6),(166.7,-46.2),(167,-45.1),(173,-40.9)),((174.6,-36.2),(176,-37.6),(178.5,-37.7),(178,-39.2),(177.2,-39.1),(175.2,-41.7),(174.9,-39.9),(173.8,-39.5),(174.7,-37.4),(172.6,-34.5),(174.6,-36.2)),((50.1,-13.6),(50.4,-15.7),(49.7,-15.7),(47.1,-24.9),(45.4,-25.6),(44,-25),(43.3,-22.1),(44.4,-20.1),(44.4,-16.2),(47.7,-14.6),(49.2,-12),(50.1,-13.6)),((143.6,-13.8),(145.4,-15),(146.4,-19),(148.8,-20.4),(149.7,-22.3),(150.7,-22.4),(150.9,-23.5),(152.9,-25.3),(153.6,-28.1),(153.1,-30.9),(150,-37.4),(146.3,-39),(145,-37.9),(143.6,-38.8),(140.6,-38),(139.6,-36.1),(138.1,-35.6),(138.2,-34.4),(136.8,-35.3),(137.8,-32.9),(136,-34.9),(134.3,-32.6),(131.3,-31.5),(126.1,-32.2),(123.7,-33.9),(119.9,-34),(118,-35.1),(115,-34.2),(115.7,-31.6),(113.3,-26.1),(113.8,-26.5),(113.4,-25.6),(114.2,-26.3),(113.4,-24.4),(114.1,-21.8),(114.2,-22.5),(116.7,-20.7),(120.9,-19.7),(123,-16.4),(123.9,-17.1),(123.8,-16.1),(125.7,-14.2),(127.1,-13.8),(129.6,-15),(130.6,-12.5),(132.6,-12.1),(131.8,-11.3),(132.4,-11.1),(135.3,-12.2),(136.5,-11.9),(137,-12.4),(135.5,-15),(140.2,-17.7),(141.3,-16.4),(142.5,-10.7),(143.6,-13.8)),((124.4,-10.1),(123.5,-10.2),(125.1,-8.7),(127.3,-8.4),(124.4,-10.1)),((108.6,-6.8),(112.6,-6.9),(115.7,-8.4),(114.6,-8.8),(105.4,-6.9),(106.1,-5.9),(108.6,-6.8)),((152,-5.5),(150.2,-6.3),(148.3,-5.7),(150,-5),(150.8,-5.5),(152.1,-4.1),(152,-5.5)),((130.5,-3.1),(130.8,-3.9),(127.9,-3.4),(128.1,-2.8),(130.5,-3.1)),((134.1,-1.2),(134.4,-2.8),(135.5,-3.4),(136.3,-2.3),(138.3,-1.7),(144.6,-3.9),(147.6,-6.1),(147.2,-7.4),(150.7,-10.6),(147.9,-10.1),(144.7,-7.6),(142.6,-9.3),(139.1,-8.1),(137.6,-8.4),(138.7,-7.3),(137.9,-5.4),(133.7,-3.5),(133,-4.1),(132,-2.8),(133.7,-2.2),(132.2,-2.2),(130.5,-0.9),(132.4,-0.4),(134.1,-1.2)),((125.2,1.4),(123.7,0.2),(120.2,0.2),(120.9,-1.4),(123.3,-0.6),(121.5,-1.9),(123.2,-5.3),(122.2,-5.3),(122.7,-4.5),(121.7,-4.9),(121,-2.6),(120.3,-2.9),(120.4,-5.5),(119.4,-5.4),(119.5,-3.5),(118.8,-2.8),(120,0.6),(120.9,1.3),(125.2,1.4)),((128.7,1.1),(128.1,-0.9),(127.4,1),(127.9,2.2),(128.7,1.1)),((105.8,-5.9),(104.7,-5.9),(102.6,-4.2),(95.3,5.5),(97.5,5.2),(103.8,0.1),(103.4,-0.7),(106.1,-3.1),(105.8,-5.9)),((117.9,1.8),(119,0.9),(117.8,0.8),(116.1,-4),(110.2,-2.9),(109.1,-0.5),(109.7,2),(111.2,1.9),(111.4,2.7),(113,3.1),(116.7,6.9),(119.2,5.4),(117.3,3.2),(117.9,1.8)),((126.4,8.4),(126.2,6.3),(125.8,7.3),(125.4,5.6),(124.2,6.2),(123.6,7.8),(121.9,7.2),(123.5,8.7),(123.8,8.2),(125.5,9),(125.4,9.8),(126.4,8.4)),((81.2,6.2),(80.3,6),(79.9,6.8),(80.1,9.8),(81.8,7.5),(81.2,6.2)),((124,10.3),(123,9),(122.4,9.7),(122.9,10.9),(123.3,10.3),(124.1,11.2),(124,10.3)),((118.5,9.3),(117.2,8.4),(119.5,11.4),(119.7,10.6),(118.5,9.3)),((125.5,12.2),(125.8,11),(125,11.3),(124.8,10.1),(124.3,12.6),(125.5,12.2)),((121.3,18.5),(122.2,18.5),(122.5,17.1),(121.7,14.3),(124,13.8),(124.1,12.5),(122.9,13.6),(120.6,13.9),(121,14.5),(120.1,15),(119.9,16.4),(120.3,16),(120.7,18.5),(121.3,18.5)),((-72.6,19.9),(-70.8,19.9),(-68.3,18.6),(-70.7,18.4),(-71.4,17.6),(-74.5,18.3),(-72.3,18.7),(-73.4,19.6),(-72.6,19.9)),((110.3,18.7),(108.7,18.5),(108.6,19.4),(110.8,20.1),(110.3,18.7)),((-79.7,22.8),(-74.2,20.3),(-77.8,19.9),(-77.1,20.4),(-78.7,21.6),(-81.8,22.6),(-85,21.9),(-82.3,23.2),(-79.7,22.8)),((121.2,22.8),(120.7,22),(120.1,23.6),(121.5,25.3),(122,25),(121.2,22.8)),((134.6,34.1),(134.2,33.2),(132.4,33),(132.9,34.1),(134.6,34.1)),((15.5,38.2),(15.1,36.6),(12.4,37.6),(15.5,38.2)),((9.2,41.2),(9.7,39.2),(8.8,38.9),(8.2,41),(9.2,41.2)),((141,37.1),(140.3,35.1),(137.2,34.6),(135.8,33.5),(135.1,34.6),(131,33.9),(132,33.1),(131.3,31.5),(130.2,31.4),(130.4,32.3),(129.4,33.3),(132.6,35.4),(135.7,35.5),(136.7,37.3),(137.4,36.8),(139.4,38.2),(139.9,40.6),(141.4,41.4),(141.9,39.2),(141,37.1)),((143.9,44.2),(145.3,44.4),(145.5,43.3),(143.2,42),(141.6,42.7),(141.1,41.6),(140,41.6),(139.8,42.6),(141.4,43.4),(142,45.6),(143.9,44.2)),((-123.5,48.5),(-125.7,48.8),(-128.4,50.8),(-125.8,50.3),(-123.5,48.5)),((-56.1,50.7),(-56.8,49.8),(-56.1,50.2),(-53.1,48.7),(-53.1,46.7),(-54.2,46.8),(-54.2,47.8),(-55.4,46.9),(-56.3,47.6),(-59.3,47.6),(-57.4,50.7),(-55.4,51.6),(-56.1,50.7)),((-132.7,54),(-131.7,54.1),(-132,53),(-131.2,52.2),(-133.1,53.4),(-133.2,54.2),(-132.7,54)),((143.6,50.7),(144.7,49),(143.2,49.3),(142.6,47.9),(143.5,46.1),(142.7,46.7),(142.1,46),(142.2,51),(141.6,51.9),(142.7,54.4),(143.6,50.7)),((-6.8,52.3),(-10,51.8),(-9.2,52.9),(-9.7,53.9),(-6.7,55.2),(-5.7,54.6),(-6.8,52.3)),((-3,58.6),(-4.1,57.6),(-2,57.7),(-3.1,56),(-0.4,54.5),(0.5,52.9),(1.7,52.7),(1.4,51.3),(-5.2,50),(-5.8,50.2),(-3.4,51.4),(-5.3,52),(-4.2,52.3),(-4.6,53.5),(-3.1,53.4),(-2.9,54),(-4.8,54.8),(-5,55.8),(-5.6,55.3),(-6.1,56.8),(-5,58.6),(-3,58.6)),((-85.2,65.7),(-80.1,63.7),(-87.2,63.5),(-85.9,65.7),(-85.2,65.7)),((-14.5,66.5),(-14.7,65.8),(-13.6,65.1),(-18.7,63.5),(-22.8,64),(-21.8,64.4),(-24,64.9),(-22.2,65.4),(-24.3,65.6),(-23.7,66.3),(-20.6,65.7),(-14.5,66.5)),((-175,66.6),(-171.9,66.9),(-169.9,66),(-172.5,65.4),(-173,64.3),(-178.4,65.4),(-178.7,66.1),(-179.9,65.9),(-179.4,65.4),(-180,65),(-180,69),(-174.9,67.2),(-175,66.6)),((-95.6,69.1),(-99.8,69.4),(-98.2,70.1),(-95.6,69.1)),((-90.5,69.5),(-90.6,68.5),(-89.2,69.3),(-87.4,67.2),(-85.6,68.8),(-85.5,69.9),(-82.6,69.7),(-81.3,69.2),(-82,68.1),(-81.3,67.6),(-83.3,66.4),(-85.8,66.6),(-87.3,64.8),(-93.2,62),(-94.7,58.9),(-93.2,58.8),(-92.3,57.1),(-82.3,55.1),(-82.1,53.3),(-79.9,51.2),(-78.6,52.6),(-79.8,54.7),(-76.5,56.5),(-78.5,58.8),(-77.3,59.9),(-78.1,62.3),(-73.8,62.4),(-71.4,61.1),(-69.6,61.1),(-69.3,59),(-67.6,58.2),(-64.6,60.3),(-61.4,57),(-61.8,56.3),(-57.3,54.6),(-55.8,53.3),(-55.7,52.1),(-60,50.2),(-66.4,50.2),(-71.1,46.8),(-68.7,48.3),(-65.1,49.2),(-64.2,48.7),(-65.1,48.1),(-64.5,46.2),(-61.5,45.9),(-60.5,47),(-59.8,45.9),(-65.4,43.5),(-66.2,44.5),(-64.4,45.3),(-67.1,45.1),(-70.1,43.7),(-70.8,42.3),(-70,41.6),(-74,40.8),(-74.9,38.9),(-75.5,39.5),(-75.1,38.4),(-75.9,37.2),(-76.3,39.2),(-76.3,38.1),(-77,38.2),(-75.7,35.6),(-81.3,31.4),(-80.1,26.9),(-80.4,25.2),(-81.2,25.2),(-82.9,29.1),(-84.1,30.1),(-85.1,29.6),(-86.4,30.4),(-89.2,30.3),(-89.2,29.3),(-90.2,29.1),(-93.2,29.8),(-96.6,28.3),(-97.4,27.4),(-97.9,22.4),(-96.3,19.3),(-94.4,18.1),(-91.4,18.9),(-89.6,21.3),(-86.8,21.3),(-88.9,15.9),(-85,16),(-83.1,15),(-83.9,11.4),(-82.2,9),(-79,9.6),(-76.8,8.6),(-74.9,11.1),(-71.8,12.4),(-71.1,12.1),(-71.9,11.4),(-71.7,9.1),(-71,9.9),(-71.4,11),(-69.9,12.2),(-68.2,10.6),(-64.9,10.1),(-61.9,10.7),(-62.7,10.4),(-62.4,9.9),(-60.8,9.4),(-58.5,6.8),(-54,5.8),(-51.3,4.2),(-50,1.7),(-50.4,-0.1),(-48.6,-0.2),(-48.6,-1.2),(-47.8,-0.6),(-44.9,-1.6),(-44.6,-2.7),(-40,-2.9),(-35.6,-5.1),(-34.7,-7.3),(-35.1,-9),(-39,-13.8),(-39.3,-17.9),(-40.9,-21.9),(-42,-23),(-47.6,-24.9),(-48.5,-25.9),(-48.9,-28.7),(-53.8,-34.4),(-56.2,-34.9),(-58.4,-33.9),(-56.8,-36.9),(-57.7,-38.2),(-62.3,-38.8),(-62.1,-40.7),(-65.1,-41.1),(-65,-42.1),(-63.5,-42.6),(-67.6,-46.3),(-65.6,-47.2),(-66,-48.1),(-69.1,-50.7),(-68.2,-52.3),(-70.8,-52.9),(-71.4,-53.9),(-74.9,-52.3),(-75.6,-48.7),(-74.1,-46.9),(-75.6,-46.6),(-74.4,-44.1),(-73.2,-44.5),(-72.7,-42.4),(-73.4,-42.1),(-73.7,-43.4),(-74.3,-43.2),(-73.2,-39.3),(-73.6,-37.2),(-71.4,-32.4),(-70.2,-19.8),(-70.4,-18.3),(-76,-14.6),(-79,-8.4),(-81.2,-6.1),(-81.4,-4.7),(-79.8,-2.7),(-81,-2.2),(-80.9,-1.1),(-80.1,0.8),(-77.1,3.8),(-78.2,8.3),(-79.6,8.9),(-80.5,8.1),(-80,7.5),(-80.9,7.2),(-83.5,8.4),(-85,10.1),(-85.7,9.9),(-85.7,11.1),(-87.5,13.3),(-91.7,14.1),(-94.7,16.2),(-96.6,15.7),(-103.5,18.3),(-105.5,19.9),(-106,22.8),(-111.8,28.5),(-113.1,31.2),(-114.8,31.8),(-114.7,30.2),(-109.4,23.2),(-110,22.8),(-112.2,24.7),(-112.3,26),(-115.1,27.7),(-114.2,28.6),(-117.3,33),(-120.6,34.6),(-124.4,40.3),(-123.9,45.5),(-124.7,48.2),(-123.1,48),(-122.6,47.1),(-122.8,49),(-127.4,50.8),(-127.9,52.3),(-134.1,58.1),(-147.1,60.9),(-148.2,60.7),(-148,60),(-151.7,59.2),(-150.6,61.3),(-154,59.4),(-153.3,58.9),(-154.2,58.1),(-158.4,56),(-164.8,54.4),(-158.7,57),(-157,58.9),(-162,58.7),(-161.9,59.6),(-163.8,59.8),(-166.1,61.5),(-164.6,63.1),(-160.8,63.8),(-161.5,64.4),(-160.8,64.8),(-165,64.4),(-168.1,65.7),(-164.5,66.6),(-161.7,66.1),(-166.8,68.4),(-156.6,71.4),(-136.5,68.9),(-129.1,69.8),(-128.1,70.5),(-125.8,69.5),(-124.4,70.2),(-124.3,69.4),(-121.5,69.8),(-113.9,68.4),(-115.3,67.9),(-109.9,68),(-108.9,67.4),(-107.8,67.9),(-108.8,68.3),(-108.2,68.7),(-106.2,68.8),(-101.5,67.6),(-98.4,67.8),(-98.6,68.4),(-97.7,68.6),(-96.1,68.2),(-96.1,67.3),(-94.2,69.1),(-96.5,70.1),(-96.4,71.2),(-95.2,71.9),(-91.5,70.2),(-92.4,69.7),(-90.5,69.5)),((-114.2,73.1),(-114.7,72.7),(-109.9,73),(-108.2,71.7),(-107.7,72.1),(-108.4,73.1),(-106.5,73.1),(-105.4,72.7),(-104.5,71),(-101.1,69.6),(-102.7,69.5),(-102.4,68.8),(-113.3,68.5),(-117.3,70),(-112.4,70.4),(-117.9,70.5),(-118.4,70.9),(-116.1,71.3),(-119.4,71.6),(-117.9,72.7),(-114.2,73.1)),((-76.3,73.1),(-79.5,72.7),(-80.9,73.3),(-78.1,73.7),(-76.3,73.1)),((-86.6,73.2),(-85.8,72.5),(-82.3,73.8),(-80.7,72.1),(-77.8,72.7),(-74.1,71.3),(-72.2,71.6),(-67,69.2),(-68.8,68.7),(-61.9,66.9),(-63.9,65),(-68,66.3),(-68.1,65.7),(-64.7,63.4),(-65,62.7),(-68.8,63.7),(-66.2,61.9),(-71,62.9),(-74.8,64.7),(-77.7,64.2),(-78.6,64.6),(-77.9,65.3),(-74,65.5),(-72.9,67.7),(-79,70.2),(-84.9,70),(-89.9,71.2),(-90.2,72.2),(-89.4,73.1),(-85.8,73.8),(-86.6,73.2)),((-100.4,73.8),(-97.4,73.8),(-98.1,73),(-96.5,72.6),(-96.7,71.7),(-99.3,71.4),(-102.5,72.5),(-100.4,72.7),(-101.5,73.4),(-100.4,73.8)),((-93.2,72.8),(-95.4,72.1),(-96,73.4),(-94.5,74.1),(-90.5,73.9),(-93.2,72.8)),((-120.5,71.4),(-123.1,70.9),(-125.9,71.9),(-123.9,73.7),(-124.9,74.3),(-117.6,74.2),(-115.5,73.5),(-119.2,72.5),(-120.5,71.4)),((145.1,75.6),(144.3,74.8),(139,74.6),(137,75.3),(138.8,76.1),(145.1,75.6)),((-98.5,76.7),(-97.7,76.3),(-98.2,75),(-102.5,75.6),(-102.6,76.3),(-98.5,76.7)),((-108.2,76.2),(-105.7,75.5),(-112.2,74.4),(-113.9,74.7),(-111.8,75.2),(-117.7,75.2),(-115.4,76.5),(-110.8,75.5),(-109.1,75.5),(-110.5,76.4),(-109.6,76.8),(-108.2,76.2)),((57.5,70.7),(53.7,70.8),(51.5,72),(55.9,74.6),(55.6,75.1),(61.2,76.3),(68.9,76.5),(58.5,74.3),(55.4,72.4),(55.6,71.5),(57.5,70.7)),((-94.7,77.1),(-91.6,76.8),(-89.2,75.6),(-81.1,75.7),(-79.8,74.9),(-89.8,74.5),(-97.1,76.8),(-94.7,77.1)),((-116.2,77.6),(-117.1,76.5),(-122.9,76.1),(-119.1,77.5),(-116.2,77.6)),((107,77),(114.1,75.8),(109.4,74.2),(119,73.1),(127,73.6),(128.6,73),(129.1,72.4),(128.5,72),(129.7,71.2),(131.3,70.8),(132.3,71.8),(139.9,71.5),(139.1,72.4),(140.5,72.8),(149.5,72.2),(153,70.8),(159,70.9),(159.7,69.7),(160.9,69.4),(167.8,69.6),(169.6,68.7),(170.8,69),(170,69.7),(170.5,70.1),(175.7,69.9),(180,69),(180,65),(177.4,64.6),(179.4,63),(179.2,62.3),(173.7,61.7),(170.3,59.9),(168.9,60.6),(163.5,59.9),(162,58.2),(163.2,57.6),(163.1,56.2),(162.1,56.1),(162.1,54.9),(160.4,54.3),(160,53.2),(158.5,53),(156.8,51),(155.4,55.4),(155.9,56.8),(163.7,61.1),(164.5,62.6),(160.1,60.5),(159.3,61.8),(156.7,61.4),(154.2,59.8),(155,59.1),(151.3,58.8),(151.3,59.5),(149.8,59.7),(142.2,59),(135.1,54.7),(138.2,53.8),(139.9,54.2),(141.4,52.2),(140.1,48.4),(136.9,45.1),(133.5,42.8),(132.3,43.3),(130.9,42.6),(129.7,40.9),(127.5,39.8),(129.5,36.8),(129.1,35.1),(126.5,34.4),(126.1,36.7),(126.9,36.9),(124.7,38.1),(125.3,39.6),(121.1,38.9),(122.2,40.4),(121.6,40.9),(118,39.2),(117.5,38.7),(118.9,37.4),(122.4,37.5),(122.5,36.9),(121.1,36.7),(119.2,34.9),(121.9,31.7),(121.3,30.7),(122.1,29.8),(121.7,28.2),(118.7,24.5),(115.9,22.8),(110.8,21.4),(110.4,20.3),(109.9,21.4),(108.1,21.6),(105.9,19.8),(106.4,18),(108.9,15.3),(109.2,11.7),(105.2,8.6),(105.1,9.9),(103.5,10.6),(102.6,12.2),(100.8,12.6),(101,13.4),(100.1,13.4),(99.2,9.2),(99.9,9.2),(100.5,7.4),(103.4,4.9),(104.2,1.3),(101.4,2.8),(100.1,6.5),(98.5,8.4),(98.3,7.8),(98.8,11.4),(97.2,16.9),(95.4,15.7),(94.2,16),(93.7,19.7),(91.4,22.8),(90.5,22.8),(90.3,21.8),(87,21.5),(87,20.7),(82.2,16.6),(80.3,15.9),(79.9,10.4),(77.5,8),(73.5,16),(72.6,21.4),(70.5,20.9),(66.4,25.4),(57.4,25.7),(57,27),(53.5,26.8),(51.5,27.9),(50.1,30.1),(48,30),(50.8,24.8),(51,26),(51.6,25.8),(51.8,24),(54,24.1),(56.4,26.4),(56.8,24.2),(58.7,23.6),(59.8,22.3),(57.8,20.2),(57.7,18.9),(55.3,17.2),(52.4,16.4),(52.2,15.6),(48.7,14),(43.5,12.6),(42.3,17.5),(39.1,21.3),(38.5,23.7),(34.6,28.1),(35,29.4),(33.9,27.6),(32.4,29.9),(35.7,23.9),(35.5,23.1),(36.9,22),(37.5,18.6),(39.3,15.9),(43.1,12.7),(42.7,11.7),(44.6,10.4),(51.1,12),(51,10.6),(48.6,5.3),(40.3,-2.6),(39.2,-4.7),(38.7,-5.9),(40.5,-10.8),(40.8,-14.7),(39.5,-16.7),(34.8,-19.8),(35.5,-24.1),(32.6,-25.7),(32.2,-28.8),(28.2,-32.8),(25.8,-33.9),(20.1,-34.8),(18.4,-34.1),(18.2,-31.7),(15.2,-27.1),(14.3,-22.1),(11.8,-18.1),(11.8,-15.8),(13.7,-10.7),(11.9,-5),(8.8,-1.1),(9.8,3.1),(8.5,4.8),(5.9,4.3),(4.3,6.3),(-2,4.7),(-9,4.8),(-12.4,7.3),(-16.7,12.4),(-17.6,14.7),(-16.1,18.1),(-17,21.9),(-14.4,26.3),(-9.6,29.9),(-9.3,32.6),(-6.9,34.1),(-5.9,35.8),(-2.2,35.2),(1.5,36.6),(9.5,37.4),(11.1,36.9),(10.3,33.8),(19.1,30.3),(20.1,31),(20.1,32.2),(21.5,32.8),(28.9,30.9),(31,31.6),(33.8,31),(36,34.6),(36.2,36.7),(32.5,36.1),(30.6,36.7),(29.7,36.1),(27.6,36.7),(26.2,39.5),(29.2,41.2),(33.5,42),(38.3,40.9),(40.4,41),(41.7,42),(36.7,45.2),(39.1,47.3),(35,46.3),(36.3,45.1),(33.9,44.4),(32.5,45.3),(33.6,45.9),(30.7,46.6),(27.7,42.6),(28.8,41.1),(26.4,40.2),(25.4,40.9),(23.7,40.7),(24.4,40.1),(22.6,40.3),(24,37.7),(23.1,37.9),(23.2,36.4),(22.5,36.4),(19.4,40.3),(19.4,41.9),(13.1,45.7),(12.3,45.4),(12.6,44.1),(18.5,40.2),(16.9,40.4),(16.4,39.8),(17.1,38.9),(16.1,38),(15.4,40),(8.9,44.4),(6.5,43.1),(3.1,43.1),(3,41.9),(0.8,41),(-0.3,39.3),(0.1,38.7),(-2.1,36.7),(-4.4,36.7),(-5.4,35.9),(-6.5,36.9),(-8.9,36.9),(-9.4,43),(-8,43.7),(-1.9,43.4),(-1.4,44),(-1.2,46),(-4.6,48.7),(-1.6,48.6),(-1.9,49.8),(-1,49.3),(1.3,50.1),(1.6,50.9),(3.8,51.6),(4.7,53.1),(8.1,53.5),(8.8,54),(8.1,55.5),(8.5,57.1),(10.6,57.7),(10.9,56.5),(9.7,55.5),(10.9,54),(12.5,54.5),(14.1,53.8),(17.6,54.9),(19.7,54.4),(21.3,55.2),(21.6,57.4),(22.5,57.8),(24.1,57),(24.4,58.4),(23.3,59.2),(29.1,60),(28.1,60.5),(22.9,59.8),(21.3,60.7),(21.5,63.2),(25.4,65.1),(23.9,66),(22.2,65.7),(21.4,64.4),(17.8,62.7),(17.1,61.3),(18.8,60.1),(16.8,58.7),(15.9,56.1),(12.9,55.4),(10.4,59.5),(8.4,58.3),(5.7,58.6),(5,62),(10.5,64.5),(16.4,68.6),(24.5,71),(28.2,71.2),(31.3,70.5),(30,70.2),(31.1,69.6),(36.5,69.1),(41.1,67.5),(41.1,66.8),(38.4,66),(33.2,66.6),(34.8,65.9),(34.9,64.4),(37,63.8),(36.5,64.8),(37.2,65.1),(39.6,64.5),(40.4,64.8),(39.8,65.5),(42.1,66.5),(43.9,66.1),(44.5,66.8),(43.5,68.6),(46.3,68.3),(46.8,67.7),(45.6,67.6),(46.3,66.7),(53.7,68.9),(54.5,68.8),(53.5,68.2),(58.8,68.9),(59.9,68.3),(61.1,68.9),(60,69.5),(60.6,69.9),(68.5,68.1),(69.2,68.6),(66.9,69.5),(66.7,71),(69.2,72.8),(72.6,72.8),(71.8,71.4),(72.8,70.4),(72.6,69),(73.7,68.4),(71.3,66.3),(72.4,66.2),(75.1,67.8),(74.5,68.3),(74.9,69),(73.6,69.6),(74.4,70.6),(73.1,71.4),(74.9,72.1),(74.7,72.8),(75.7,72.3),(75.3,71.3),(76.4,71.2),(75.9,71.9),(77.6,72.3),(81.5,71.8),(80.5,73.6),(86.8,73.9),(86,74.5),(87.2,75.1),(100.8,76.4),(104.4,77.7),(106.1,77.4),(104.7,77.1),(107,77)),((24.7,77.9),(20.7,77.7),(21.4,77.9),(20.8,78.3),(22.9,78.5),(24.7,77.9)),((-100.1,78.3),(-99.7,77.9),(-105.2,78.4),(-104.2,78.7),(-105.5,79.3),(-100.1,78.3)),((105.1,78.3),(99.4,77.9),(102.1,79.3),(105.4,78.7),(105.1,78.3)),((18.3,79.7),(21.5,79),(19,78.6),(17.1,76.8),(15.9,76.8),(10.4,79.7),(18.3,79.7)),((25.4,80.4),(27.4,80.1),(23,79.4),(17.4,80.3),(25.4,80.4)),((51.1,80.5),(47.6,80),(44.8,80.6),(51.1,80.5)),((99.9,78.9),(95,79),(91.2,80.3),(95.9,81.3),(100.2,79.8),(99.9,78.9)),((-87,79.7),(-85.8,79.3),(-89,78.3),(-92.9,78.3),(-94,78.8),(-93.1,79.4),(-96.7,80.2),(-92.4,81.3),(-87,79.7)),((-68.5,83.1),(-61.9,82.4),(-67.7,81.5),(-65.5,81.5),(-71.2,79.8),(-76.9,79.3),(-75.5,79.2),(-76.2,79),(-75.4,78.5),(-79.8,77.2),(-77.9,76.8),(-80.6,76.2),(-89.5,76.5),(-89.6,77),(-87.8,77.2),(-88.3,77.9),(-85,77.5),(-88,78.4),(-85.1,79.3),(-86.9,80.3),(-81.8,80.5),(-87.6,80.5),(-91.6,81.9),(-79.3,83.1),(-68.5,83.1)),((-27.1,83.5),(-20.8,82.7),(-31.9,82.2),(-22.1,81.7),(-23.2,81.2),(-15.8,81.9),(-12.2,81.3),(-20,80.2),(-17.7,80.1),(-19.7,78.8),(-19.7,77.6),(-18.5,77),(-21.7,76.6),(-19.8,76.1),(-19.6,75.2),(-20.7,75.2),(-19.4,74.3),(-23.6,73.3),(-22.3,72.2),(-24.8,72.3),(-22.1,71.5),(-21.8,70.7),(-23.5,70.5),(-25.5,71.4),(-25.2,70.8),(-26.4,70.2),(-22.3,70.1),(-39.8,65.5),(-41.2,63.5),(-42.8,62.7),(-42.4,61.9),(-43.4,60.1),(-48.3,60.9),(-51.6,63.6),(-54,67.2),(-53,68.4),(-51.5,68.7),(-50.9,69.9),(-54.7,69.6),(-54.4,70.8),(-51.4,70.6),(-55.8,71.7),(-54.7,72.6),(-58.6,75.5),(-68.5,76.1),(-71.4,77),(-66.8,77.4),(-73.3,78),(-65.7,79.4),(-65.3,79.8),(-68,80.1),(-62.2,81.3),(-62.7,81.8),(-50.4,82.4),(-44.5,81.7),(-46.8,82.6),(-38.6,83.5),(-27.1,83.5))]

_LON_MIN, _LON_MAX = -180.0, 180.0
_LAT_MAX, _LAT_MIN = 85.0, -65.0

# Last map label placements (for preview/report verification):
# [{number, dot:(x,y), label:(cx,cy), ring, leader:bool}] in box coords.
_LAST_MAP_PLACEMENTS = []


def _project(lon, lat, box):
    x0, y0, x1, y1 = box
    x = x0 + (lon - _LON_MIN) / (_LON_MAX - _LON_MIN) * (x1 - x0)
    y = y0 + (_LAT_MAX - lat) / (_LAT_MAX - _LAT_MIN) * (y1 - y0)
    return x, y


def draw_world_map(draw, box, pins, palette, font=None, pin_radius=7.5):
    """Draw world map + numbered pins inside box=(x0,y0,x1,y1).

    pins: iterable of dicts {number, story_id, lon, lat, region?}.
    v2 (A10 B2): Ø6px dot at the TRUE projected point (never moved);
    11px-bold white number on a region-colour disc beside the dot.
    Label placement is deterministic (candidates E, NE, SE, W, NW,
    SW, N, S at ring 1, then ring 2/3 with a 1px leader line);
    collisions offset the LABEL only. pin_radius kept for signature
    compatibility (dots fixed Ø6px). Header/legend/caption by A12.
    """
    pal = _pal(palette)
    _clipped(draw, box,
             lambda d, b: _draw_map(d, b, pins, pal, font, pin_radius))


def _draw_map(draw, box, pins, pal, font, pin_radius):
    global _LAST_MAP_PLACEMENTS
    box = tuple(float(v) for v in box)
    x0, y0, x1, y1 = box
    draw.rectangle(box, fill=pal["card"])
    # faint graticule every 30 degrees
    grat = pal["card_edge"]
    for lon in range(-150, 181, 30):
        gx, _ = _project(lon, 0, box)
        draw.line([gx, y0, gx, y1], fill=grat, width=1)
    for lat in range(-60, 61, 30):
        _, gy = _project(0, lat, box)
        draw.line([x0, gy, x1, gy], fill=grat, width=1)
    land = _tint(pal, pal["navy_light"], 0.68)
    edge = _tint(pal, pal["grey"], 0.25)
    for poly in _LAND:
        pts = [_project(lon, lat, box) for lon, lat in poly]
        draw.polygon(pts, fill=land, outline=edge)
    # pins: dot at TRUE point; label disc placed deterministically
    items = []
    for p in pins:
        px, py = _project(float(p["lon"]), float(p["lat"]), box)
        region = p.get("region") or _STORY_REGION.get(p.get("story_id"), "Global")
        items.append({"n": p["number"], "region": region, "dot": (px, py)})
    items.sort(key=lambda it: it["n"])
    fnt = _sized_font(font, 11, bold=True)
    dot_r = 3.0  # Ø6px
    dirs = [(1, 0), (1, -1), (1, 1), (-1, 0), (-1, -1), (-1, 1),
            (0, -1), (0, 1)]  # E, NE, SE, W, NW, SW, N, S
    placed = []  # label bboxes (with pad) already taken
    placements = []
    for it in items:
        label = str(it["n"])
        tb = draw.textbbox((0, 0), label, font=fnt)
        tw, th = tb[2] - tb[0], tb[3] - tb[1]
        lr = max(7.0, tw / 2.0 + 3.0, th / 2.0 + 3.0)
        dx, dy = it["dot"]
        chosen = None
        for ring, gap in ((1, 2.0), (2, 9.0), (3, 16.0)):
            for ux, uy in dirs:
                norm = math.hypot(ux, uy)
                dist = dot_r + lr + gap
                cx = dx + ux / norm * dist
                cy = dy + uy / norm * dist
                bb = (cx - lr, cy - lr, cx + lr, cy + lr)
                if (bb[0] < x0 + 0.5 or bb[1] < y0 + 0.5
                        or bb[2] > x1 - 0.5 or bb[3] > y1 - 0.5):
                    continue
                ok = True
                for pb in placed:
                    if not (bb[2] + 1.0 <= pb[0] or pb[2] + 1.0 <= bb[0]
                            or bb[3] + 1.0 <= pb[1] or pb[3] + 1.0 <= bb[1]):
                        ok = False
                        break
                if ok:
                    for other in items:
                        if other is it:
                            continue
                        ox, oy = other["dot"]
                        if (bb[0] - dot_r <= ox <= bb[2] + dot_r
                                and bb[1] - dot_r <= oy <= bb[3] + dot_r):
                            ok = False
                            break
                if ok:
                    chosen = (cx, cy, ring, bb)
                    break
            if chosen:
                break
        if chosen is None:  # fallback: E at ring 3, clamped inside box
            cx = min(max(dx + dot_r + lr + 16.0, x0 + lr + 0.5), x1 - lr - 0.5)
            cy = min(max(dy, y0 + lr + 0.5), y1 - lr - 0.5)
            chosen = (cx, cy, 3, (cx - lr, cy - lr, cx + lr, cy + lr))
        cx, cy, ring, bb = chosen
        placed.append(bb)
        it["label_c"] = (cx, cy)
        it["lr"] = lr
        it["tw"], it["th"], it["tb"] = tw, th, tb
        placements.append({"number": it["n"], "dot": it["dot"],
                           "label": (cx, cy), "ring": ring,
                           "leader": ring > 1})
    _LAST_MAP_PLACEMENTS = placements
    # leader lines first (under dots/discs), 1px, region colour
    for it, pl in zip(items, placements):
        if pl["leader"]:
            draw.line([it["dot"][0], it["dot"][1],
                       it["label_c"][0], it["label_c"][1]],
                      fill=_region_color(pal, it["region"]), width=1)
    # dots at true points
    for it in items:
        dx, dy = it["dot"]
        draw.ellipse([dx - dot_r, dy - dot_r, dx + dot_r, dy + dot_r],
                     fill=_region_color(pal, it["region"]),
                     outline=pal["white"], width=1)
    # label discs + numbers
    for it in items:
        cx, cy = it["label_c"]
        lr = it["lr"]
        draw.ellipse([cx - lr, cy - lr, cx + lr, cy + lr],
                     fill=_region_color(pal, it["region"]),
                     outline=pal["white"], width=1)
        tb = it["tb"]
        draw.text((cx - it["tw"] / 2 - tb[0], cy - it["th"] / 2 - tb[1]),
                  str(it["n"]), font=fnt, fill=pal["white"])


# ---------------------------------------------------------------- markets chart

# Last chart row text bboxes (for preview/report verification):
# [{instrument, name_bbox, value_bbox}] in box coords.
_LAST_CHART_BBOXES = []


def _parse_pct(change):
    s = str(change).strip().rstrip("%")
    try:
        return float(s)
    except ValueError:
        return 0.0


def draw_markets_chart(draw, box, rows, palette, font=None):
    """Draw the markets bar chart inside box=(x0,y0,x1,y1) (172x72).

    rows: [{instrument, value, change}] (copy.json feature_4
    table_rows). One row per instrument at pitch = box_h / len(rows)
    (12px at 172x72): name left (11px), horizontal bar proportional
    to the % move around a visible zero line (up = up-green,
    down = ink_soft; NO red per A10 C8), "value change" right-aligned
    (11px). Bar zone is measured from the actual font at runtime.
    Deterministic; no other text.
    """
    pal = _pal(palette)
    _clipped(draw, box, lambda d, b: _draw_chart(d, b, rows, pal, font))


def _draw_chart(draw, box, rows, pal, font):
    global _LAST_CHART_BBOXES
    x0, y0, x1, y1 = (float(v) for v in box)
    rows = list(rows)
    if not rows:
        _LAST_CHART_BBOXES = []
        return
    fnt = _sized_font(font, 11, bold=False)
    pitch = (y1 - y0) / len(rows)
    parsed = []
    name_w = 0.0
    val_w = 0.0
    for r in rows:
        name = str(r.get("instrument", ""))
        val = "%s %s" % (r.get("value", ""), r.get("change", ""))
        pct = _parse_pct(r.get("change", "0"))
        nb = draw.textbbox((0, 0), name, font=fnt)
        vb = draw.textbbox((0, 0), val, font=fnt)
        name_w = max(name_w, nb[2] - nb[0])
        val_w = max(val_w, vb[2] - vb[0])
        parsed.append({"name": name, "val": val, "pct": pct,
                       "nb": nb, "vb": vb})
    # bar zone between name column and value column
    zone_x0 = x0 + name_w + 3.0
    zone_x1 = x1 - val_w - 3.0
    if zone_x1 - zone_x0 < 8.0:  # very tight: shrink gaps
        zone_x0 = x0 + name_w + 1.0
        zone_x1 = x1 - val_w - 1.0
    zone_w = max(zone_x1 - zone_x0, 1.0)
    max_up = max([p["pct"] for p in parsed] + [0.0])
    max_dn = max([-p["pct"] for p in parsed] + [0.0])
    span = max_up + max_dn
    if span <= 0:
        span = 1.0
    zero_x = zone_x0 + zone_w * (max_dn / span)
    scale = zone_w / span
    bar_h = min(6.0, pitch - 5.0)
    # zero line (visible, full height)
    draw.line([zero_x, y0 + 1, zero_x, y1 - 1], fill=pal["grey"], width=1)
    bboxes = []
    for i, p in enumerate(parsed):
        ry = y0 + i * pitch
        cy = ry + pitch / 2.0
        # bar
        bx1 = zero_x + p["pct"] * scale
        bx0, bx1 = min(zero_x, bx1), max(zero_x, bx1)
        if bx1 - bx0 < 1.0:
            bx1 = bx0 + 1.0
        col = pal["up"] if p["pct"] >= 0 else pal["ink_soft"]
        draw.rectangle([bx0, cy - bar_h / 2, bx1, cy + bar_h / 2], fill=col)
        # name (left), positioned by bbox so glyphs centre in the row
        nb = p["nb"]
        nth = nb[3] - nb[1]
        ny = ry + (pitch - nth) / 2.0
        draw.text((x0 + 1 - nb[0], ny - nb[1]), p["name"], font=fnt,
                  fill=pal["ink"])
        name_bbox = (x0 + 1, ny, x0 + 1 + (nb[2] - nb[0]), ny + nth)
        # value + change (right-aligned)
        vb = p["vb"]
        vth = vb[3] - vb[1]
        vw = vb[2] - vb[0]
        vy = ry + (pitch - vth) / 2.0
        draw.text((x1 - 1 - vw - vb[0], vy - vb[1]), p["val"], font=fnt,
                  fill=pal["ink"])
        val_bbox = (x1 - 1 - vw, vy, x1 - 1, vy + vth)
        bboxes.append({"instrument": p["name"], "name_bbox": name_bbox,
                       "value_bbox": val_bbox})
    _LAST_CHART_BBOXES = bboxes


# ---------------------------------------------------------------- timeline

def draw_timeline_axis(draw, box, pins, palette, font=None, hour_labels=True):
    """Draw the UTC axis (line 2 of the timeline strip) inside box.

    Axis spans the full box width: 00:00 at x0, 24:00 at x1. Ticks
    every 3h with small hour labels below. Dots (navy, r=3) at each
    pin's true UTC position; pins carry 'utc' "HH:MM" (preferred) or
    'x_px' (absolute page x from layout.json). The text strip (line 1)
    is drawn by A12.
    """
    pal = _pal(palette)
    box = tuple(float(v) for v in box)
    # normalize x_px pins to offsets from box left edge (clip-safe)
    norm = []
    for p in pins:
        q = dict(p)
        if not q.get("utc") and q.get("x_px") is not None:
            q["x_off"] = float(q["x_px"]) - box[0]
        norm.append(q)
    _clipped(draw, box,
             lambda d, b: _draw_axis(d, b, norm, pal, font, hour_labels),
             transparent=True)


def _draw_axis(draw, box, pins, pal, font, hour_labels):
    x0, y0, x1, y1 = (float(v) for v in box)
    box_h = y1 - y0
    # Thin-strip mode (upgrade: 984x6 box, hour_labels=False): centre
    # the axis, keep dots <=5px diameter and 3h ticks inside the box.
    thin = box_h <= 8
    if thin:
        axis_y = y0 + box_h / 2.0
        draw.line([x0, axis_y, x1, axis_y], fill=pal["rule"], width=1)
        for hr in range(0, 25, 3):
            tx = x0 + hr / 24.0 * (x1 - x0)
            draw.line([tx, axis_y - 1.5, tx, axis_y + 1.5],
                      fill=pal["rule"], width=1)
        dot_r = 2.0
    else:
        axis_y = y0 + 4
        draw.line([x0, axis_y, x1, axis_y], fill=pal["rule"], width=2)
        fnt = _font(font, 8)
        for hr in range(0, 25, 3):
            tx = x0 + hr / 24.0 * (x1 - x0)
            draw.line([tx, axis_y, tx, axis_y + 4], fill=pal["rule"], width=1)
            if hour_labels:
                label = "%02d" % hr
                tb = draw.textbbox((0, 0), label, font=fnt)
                tw = tb[2] - tb[0]
                lx = min(max(tx - tw / 2 - tb[0], x0), x1 - tw)
                draw.text((lx, axis_y + 5), label, font=fnt, fill=pal["grey"])
        dot_r = 3.0
    for p in pins:
        if p.get("utc"):
            hh, mm = str(p["utc"]).split(":")
            mins = int(hh) * 60 + int(mm)
            px = x0 + mins / 1440.0 * (x1 - x0)
        elif p.get("x_off") is not None:
            px = x0 + float(p["x_off"])
        elif p.get("x_px") is not None:
            px = float(p["x_px"])
        else:
            continue
        draw.ellipse([px - dot_r, axis_y - dot_r, px + dot_r, axis_y + dot_r],
                     fill=pal["navy"], outline=pal["white"], width=1)
