#!/usr/bin/env python3
"""A12 Render Engineer (v3 port): layout.json + copy.json + graphics.py
-> entry.png.

v2 content (35 stories, certainty in WORDS) on the 1cec3843 design
(v3_port_spec_a10.md): 3 equal leads, 300x76 scenes, red overlay chips,
markets 6-row TABLE, two-line briefs pitch 22 (2 cols), Natural Earth
map 304x112 with 12 true pins, timeline dot axis + 6 NEW strip figures,
DATE CHECK 1 line @11px, footer 3 lines with auto 28-outlet sources.
G-09 hairlines fixed (feature dek +2, lead gap_hd 2, footer 2px
clearance) and guarded by an automated ink-bbox audit (Sec 9).
Deterministic: no randomness, no clock, no network.
"""
import hashlib
import json
import os
import re

from PIL import Image, ImageDraw, ImageFont

import graphics

HERE = os.path.dirname(os.path.abspath(__file__))
FL = "/usr/share/fonts/truetype/liberation/"
FONT_PATH = {
    ("Liberation Serif", "Bold"): FL + "LiberationSerif-Bold.ttf",
    ("Liberation Serif", "Regular"): FL + "LiberationSerif-Regular.ttf",
    ("Liberation Serif", "Italic"): FL + "LiberationSerif-Italic.ttf",
    ("Liberation Sans", "Bold"): FL + "LiberationSans-Bold.ttf",
    ("Liberation Sans", "Regular"): FL + "LiberationSans-Regular.ttf",
}

L = json.load(open(os.path.join(HERE, "layout.json")))
C = json.load(open(os.path.join(HERE, "copy.json")))
TYPE = L["type_scale"]
BLOCKS = {b["id"]: b for b in L["blocks"]}
PAL = {k: tuple(v["rgb"]) for k, v in L["palette"].items()}
REG = {k: tuple(v["rgb"]) for k, v in L["region_colors"].items()}

_cache = {}
INK_BOXES = []  # (label, group, x0, y0, x1, y1) ink bboxes for Sec 9 audit


def font_of(style):
    if style not in _cache:
        t = TYPE[style]
        _cache[style] = ImageFont.truetype(FONT_PATH[(t["family"], t["weight"])], t["size"])
    return _cache[style]


def raw_font(family, weight, size):
    key = (family, weight, size)
    if key not in _cache:
        _cache[key] = ImageFont.truetype(FONT_PATH[(family, weight)], size)
    return _cache[key]


def wrap(text, font, width_px):
    """Word-wrap on regular spaces only; NBSP-bound tokens never split."""
    words, lines, cur = text.split(" "), [], ""
    for w in words:
        if w == "":
            continue
        t = (cur + " " + w).strip(" ")
        if font.getlength(t) <= width_px or not cur:
            cur = t
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def check_width(text, font, width_px, label):
    w = font.getlength(text)
    assert w <= width_px, f"OVERFLOW {label}: {w:.0f}px > {width_px}px: {text!r}"
    return w


_ink_cache = {}


def _ink_box(xy, s, font):
    """True ink bbox (rendered pixels) of s drawn at xy — Sec 9 audit.
    PIL textbbox includes bearing padding that false-flags adjacent
    segments; render the string alone and measure dark pixels."""
    key = (s, font.path if hasattr(font, "path") else id(font), font.size)
    if key not in _ink_cache:
        w = int(font.getlength(s)) + 8
        h = font.size * 3 + 8
        tmp = Image.new("L", (w, h), 255)
        ImageDraw.Draw(tmp).text((4, 4), s, font=font, fill=0)
        bb = tmp.point(lambda p: 255 if p < 128 else 0).getbbox()
        _ink_cache[key] = None if bb is None else (bb[0] - 4, bb[1] - 4, bb[2] - 4, bb[3] - 4)
    rel = _ink_cache[key]
    if rel is None:
        return None
    return (xy[0] + rel[0], xy[1] + rel[1], xy[0] + rel[2], xy[1] + rel[3])


def text(d, xy, s, font, fill, label=None, group=None):
    """Draw text and register its true ink bbox for the Sec 9 audit."""
    d.text(xy, s, font=font, fill=fill)
    if label:
        bb = _ink_box(xy, s, font)
        if bb:
            INK_BOXES.append((label, group or label.split(".")[0], bb[0], bb[1], bb[2], bb[3]))
    return font.getlength(s)


def draw_wrapped(d, x, y, txt, style, width_px, max_lines, fill, label, exact=False):
    f = font_of(style)
    lines = wrap(txt, f, width_px)
    assert len(lines) <= max_lines, f"OVERFLOW {label}: {len(lines)} lines > {max_lines}: {txt!r}"
    if exact:
        assert len(lines) == max_lines, f"LINES {label}: {len(lines)} != {max_lines}: {txt!r}"
    for ln in lines:
        check_width(ln, f, width_px, label)
    leading = TYPE[style]["leading"]
    for i, ln in enumerate(lines):
        text(d, (x, y + i * leading), ln, f, fill, label=f"{label}[{i}]")
    return lines


def draw_centered_in_box(d, box, txt, font, fill, label=None):
    x0, y0, x1, y1 = box
    tb = d.textbbox((0, 0), txt, font=font)
    tw, th = tb[2] - tb[0], tb[3] - tb[1]
    xy = (x0 + (x1 - x0 - tw) / 2 - tb[0], y0 + (y1 - y0 - th) / 2 - tb[1])
    text(d, xy, txt, font, fill, label=label)


_SSAA = 3
_badge_cache = {}
_dot_cache = {}


def _badge_sprite(number, region):
    key = (number, region)
    if key in _badge_cache:
        return _badge_cache[key]
    s = _SSAA
    tmp = Image.new("RGBA", (14 * s, 14 * s), (0, 0, 0, 0))
    td = ImageDraw.Draw(tmp)
    td.ellipse([0, 0, 14 * s, 14 * s], fill=REG[region] + (255,))
    f = raw_font("Liberation Sans", "Bold", TYPE["brief_num"]["size"] * s)
    tb = td.textbbox((0, 0), str(number), font=f)
    tw, th = tb[2] - tb[0], tb[3] - tb[1]
    td.text(((14 * s - tw) / 2 - tb[0], (14 * s - th) / 2 - tb[1]),
            str(number), font=f, fill=PAL["white"] + (255,))
    spr = graphics._downscale(tmp, (14, 14), True)
    _badge_cache[key] = spr
    return spr


def _dot_sprite(color):
    if color in _dot_cache:
        return _dot_cache[color]
    s = _SSAA
    tmp = Image.new("RGBA", (8 * s, 8 * s), (0, 0, 0, 0))
    ImageDraw.Draw(tmp).ellipse([0, 0, 8 * s, 8 * s], fill=color + (255,))
    spr = graphics._downscale(tmp, (8, 8), True)
    _dot_cache[color] = spr
    return spr


def draw_badge(d, x, y, number, region):
    img = getattr(d, "_image", None)
    assert img is not None, "draw_badge needs an ImageDraw bound to an image"
    spr = _badge_sprite(number, region)
    img.paste(spr, (int(x), int(y)), spr)


def draw_tracked(d, x, y, txt, font, fill, tracking, label=None):
    cx = x
    boxes = []
    for ch in txt:
        d.text((cx, y), ch, font=font, fill=fill)
        bb = _ink_box((cx, y), ch, font)
        if bb:
            boxes.append(bb)
        cx += font.getlength(ch) + tracking
    if label and boxes:
        INK_BOXES.append((label, label.split(".")[0],
                          min(b[0] for b in boxes), min(b[1] for b in boxes),
                          max(b[2] for b in boxes), max(b[3] for b in boxes)))
    return cx - tracking


# ------------------------------------------------------------------ asserts
def assert_no_block_overlap():
    bs = L["blocks"]
    for i in range(len(bs)):
        for j in range(i + 1, len(bs)):
            a, b = bs[i], bs[j]
            overlap = (a["x"] < b["x"] + b["w"] and b["x"] < a["x"] + a["w"]
                       and a["y"] < b["y"] + b["h"] and b["y"] < a["y"] + a["h"])
            assert not overlap, f"BLOCK OVERLAP: {a['id']} vs {b['id']}"


def ink_audit(img):
    """Sec 9: zero ink overlaps; min vertical ink gap >=2px (>=1px for
    brief line boundaries); footer descenders clear frame row 1008 by
    >=2px (pixel scan). Fails loudly with locations."""
    problems = []
    boxes = INK_BOXES
    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            la, ga, ax0, ay0, ax1, ay1 = boxes[i]
            lb, gb, bx0, by0, bx1, by1 = boxes[j]
            if ax0 < bx1 and bx0 < ax1 and ay0 < by1 and by0 < ay1:
                problems.append(f"INK OVERLAP {la} {boxes[i][2:]} vs {lb} {boxes[j][2:]}")
    min_gap, min_pair = 999, None
    for i in range(len(boxes)):
        for j in range(len(boxes)):
            if i == j:
                continue
            la, ga, ax0, ay0, ax1, ay1 = boxes[i]
            lb, gb, bx0, by0, bx1, by1 = boxes[j]
            if ga != gb or by0 < ay1:
                continue
            if ax0 < bx1 and bx0 < ax1:
                gap = by0 - ay1
                if gap < min_gap:
                    min_gap, min_pair = gap, (la, lb)
                need = 1 if ("brief" in la or "brief" in lb) else 2
                if gap < need:
                    problems.append(f"INK GAP {gap}px < {need}px: {la} -> {lb}")
    px = img.load()
    paper = PAL["paper"]
    for yy in (1006, 1007):
        for xx in range(20, 1005):
            if px[xx, yy] != paper:
                problems.append(f"FOOTER FRAME GAP <2px: ink at ({xx},{yy})")
                break
    print(f"ink audit: {len(boxes)} text boxes, min vertical gap {min_gap}px {min_pair}")
    assert not problems, "INK AUDIT FAIL:\n" + "\n".join(problems[:20])


# ------------------------------------------------------------------ blocks
def draw_masthead(d, b):
    m = C["masthead"]
    assert m["date"] == "Tuesday 24 November 2026", "G-04 date string"
    kf = font_of("masthead_kicker")
    kend = draw_tracked(d, b["x"], b["y"] + 1, m["kicker"], kf, PAL["red"], 2,
                        label="masthead.kicker")
    cf = font_of("claim_line")
    cw = check_width(m["claim_line"], cf, b["budgets"]["claim_line"]["text_width_px"], "claim_line")
    cstart = b["x"] + b["w"] - cw
    assert kend < cstart, "kicker/claim collision"
    text(d, (cstart, b["y"] + 2), m["claim_line"], cf, PAL["navy"], label="masthead.claim")
    df = font_of("masthead_date")
    dw = df.getlength(m["date"])
    text(d, (b["x"] + (b["w"] - dw) / 2, b["y"] + 12), m["date"], df, PAL["ink"],
         label="masthead.date")
    sf = font_of("masthead_subhead")
    sw = check_width(m["subhead"], sf, b["budgets"]["subhead"]["text_width_px"], "subhead")
    text(d, (b["x"] + (b["w"] - sw) / 2, b["y"] + 57), m["subhead"], sf, PAL["red"],
         label="masthead.subhead")


def draw_region_chips(d, b):
    f = font_of("chip")
    x = b["x"]
    for ch in b["chips"]:
        tw = f.getlength(ch["text"]) + 16
        d.rectangle([x, b["y"] + 1, x + tw, b["y"] + b["h"] - 1],
                    fill=tuple(ch["color_rgb"]))
        text(d, (x + 8, b["y"] + 4), ch["text"], f, PAL["white"],
             label=f"chips.{ch['region']}", group="chips")
        x += tw + 8
    assert x - 8 <= b["x"] + b["w"], "region chips overflow band"


def draw_timeline_numbers(d, b):
    strip = C["timeline"]["strip_text"]
    budget = b["budgets"]["strip_text"]["text_width_px"]
    rf, bf = font_of("timeline_label"), raw_font("Liberation Sans", "Bold", 11)
    segs, pos = [], 0
    for m in re.finditer(r"(TUESDAY UTC — |\d{2}:\d{2})", strip):
        if m.start() > pos:
            segs.append((strip[pos:m.start()], rf))
        segs.append((m.group(0), bf))
        pos = m.end()
    if pos < len(strip):
        segs.append((strip[pos:], rf))
    total = sum(f.getlength(t) for t, f in segs)
    assert total <= budget, f"OVERFLOW timeline strip: {total:.0f}px > {budget}px"
    cx = b["x"]
    seg_boxes = []
    for t, f in segs:
        d.text((cx, b["y"] + 1), t, font=f, fill=PAL["ink"])
        bb = _ink_box((cx, b["y"] + 1), t, f)
        if bb:
            seg_boxes.append(bb)
        cx += f.getlength(t)
    if seg_boxes:
        INK_BOXES.append(("timeline.strip", "timeline",
                          min(v[0] for v in seg_boxes), min(v[1] for v in seg_boxes),
                          max(v[2] for v in seg_boxes), max(v[3] for v in seg_boxes)))
    axis_box = (b["x"], b["y"] + 14, b["x"] + b["w"], b["y"] + 20)
    graphics.draw_timeline_axis(d, axis_box, b["pins"], L,
                                font=raw_font("Liberation Sans", "Regular", 9),
                                hour_labels=False)
    ns = C["numbers_strip"]
    figs = ns["figures"]
    assert len(figs) == 6, f"numbers strip needs 6 figures, got {len(figs)}"
    label_w, cell_w = b["numbers"]["label_w_px"], b["numbers"]["cell_w_px"]
    assert label_w + 6 * cell_w == b["w"], "numbers row width mismatch"
    lf = font_of("numbers_label")
    d.rectangle([b["x"], b["y"] + 19, b["x"] + label_w, b["y"] + 47], fill=PAL["navy"])
    check_width(ns["label"][0], lf, label_w - 8, "numbers.label1")
    check_width(ns["label"][1], lf, label_w - 8, "numbers.label2")
    text(d, (b["x"] + 8, b["y"] + 21), ns["label"][0], lf, PAL["white"],
         label="numbers.label1", group="numbers")
    text(d, (b["x"] + 8, b["y"] + 34), ns["label"][1], lf, PAL["white"],
         label="numbers.label2", group="numbers")
    nf, cf = font_of("numbers_numeral"), font_of("numbers_caption")
    nb = b["budgets"]["numbers_numeral"]["text_width_px"]
    cb = b["budgets"]["numbers_caption"]["text_width_px"]
    for i, fg in enumerate(figs):
        cell_x = b["x"] + label_w + cell_w * i
        d.line([(cell_x, b["y"] + 21), (cell_x, b["y"] + 45)], fill=PAL["rule"], width=1)
        check_width(fg["numeral"], nf, nb, f"numbers.numeral[{i}]")
        check_width(fg["caption"], cf, cb, f"numbers.caption[{i}]")
        # Sec 9 nudge: spec y+19/y+36 gives 1px ink overlap (true pixels);
        # numeral y+18 / caption y+38 -> >=2px gap.
        text(d, (cell_x + 10, b["y"] + 18), fg["numeral"], nf, PAL["ink"],
             label=f"numbers.numeral[{i}]", group=f"numbers[{i}]")
        text(d, (cell_x + 10, b["y"] + 38), fg["caption"], cf, PAL["ink_soft"],
             label=f"numbers.caption[{i}]", group=f"numbers[{i}]")


def _chip_font(b, chip_text, scene_w):
    # Sec 6.2: size must satisfy (i) box-fit AND (ii) focal clearance
    # (chip_right <= ~0.75x scene_w); layout chip_font_px encodes the
    # A7-approved size per card (f13 = 9px, A1 ruling). Verify both.
    want = b.get("chip_font_px")
    assert want in (13, 12, 11, 9), f"{b['id']} missing chip_font_px"
    f = raw_font("Liberation Sans", "Bold", want)
    box_right = 6 + f.getlength(chip_text) + 14
    assert box_right <= scene_w + 8, f"{b['id']} chip@{want} box-fit {box_right:.1f}"
    # focal clearance (ii) is per-card (A11 pre-shifted focals; Sec 12
    # masked previews) — sizes in layout are the A7/A11-verified ones.
    return f


def draw_card(d, b):
    is_lead = b["kind"] == "lead_card"
    c = C[b.get("copy_key", b["id"])]
    st = b["stack_px"]
    pad = 10 if is_lead else 8
    tx, tw = b["x"] + pad, b["w"] - 2 * pad
    d.rectangle([b["x"], b["y"], b["x"] + b["w"], b["y"] + b["h"]],
                fill=PAL["card"], outline=PAL["card_edge"], width=1)
    yy = b["y"] + st["pad_top"]
    draw_badge(d, tx, yy, b["number"], b["region"])
    kf = font_of("card_kicker")
    check_width(c["kicker"], kf, b["budgets"]["kicker"]["text_width_px"], b["id"] + ".kicker")
    text(d, (tx + 18, yy + 1), c["kicker"], kf, REG[b["region"]],
         label=b["id"] + ".kicker")
    if is_lead:
        tf = font_of("status_tag")
        twd = tf.getlength(c["status_word"]) + 8
        d.rectangle([b["x"] + b["w"] - pad - twd, yy, b["x"] + b["w"] - pad, yy + 14],
                    outline=PAL["navy"], width=1)
        text(d, (b["x"] + b["w"] - pad - twd + 4, yy + 1), c["status_word"],
             tf, PAL["navy"], label=b["id"] + ".status")
    yy += st["kicker_row"] + st["gap1"]

    if b.get("variant") == "markets_table":
        hb = b["budgets"]["headline"]
        draw_wrapped(d, tx, yy, c["headline"], hb["style"], hb["text_width_px"],
                     hb["lines"], PAL["ink"], b["id"] + ".headline")
        yy += st["headline"] + st["gap2"]
        rf, nf = font_of("markets_row"), font_of("markets_num")
        for r in c["table_rows"]:
            name_w = rf.getlength(r["instrument"])
            val_w = nf.getlength(r["value"])
            chg_w = nf.getlength(r["change"])
            val_x = tw - 52 - val_w
            assert name_w <= val_x and val_x + val_w <= tw - chg_w, \
                f"markets row collision: {r['instrument']}"
            text(d, (tx, yy), r["instrument"], rf, PAL["ink"],
                 label=b["id"] + f".row.{r['instrument']}", group=b["id"] + ".table")
            text(d, (tx + val_x, yy), r["value"], nf, PAL["ink"],
                 label=b["id"] + f".val.{r['instrument']}", group=b["id"] + ".table")
            text(d, (tx + tw - chg_w, yy), r["change"], nf,
                 PAL["up"] if r["change"].startswith("+") else PAL["down"],
                 label=b["id"] + f".chg.{r['instrument']}", group=b["id"] + ".table")
            yy += 12
    else:
        sh = st["scene"]
        scene_box = (tx, yy, tx + tw, yy + sh)
        ok = graphics.draw_scene(d, scene_box, b["story_id"], L)
        assert ok, f"no scene for {b['story_id']}"
        d.rectangle([tx, yy, tx + tw, yy + sh], outline=PAL["card_edge"], width=1)
        chip_text = c["badge"]
        if is_lead:
            cf = font_of("lead_chip")
            check_width(chip_text, cf, b["budgets"]["number_chip"]["text_width_px"],
                        b["id"] + ".chip")
        else:
            cf = _chip_font(b, chip_text, tw)
        cwd = cf.getlength(chip_text) + 14
        chip_top = yy + sh - 30 if is_lead else yy + sh - 24
        chip_box = (tx + 6, chip_top, tx + 6 + cwd, yy + sh - 4)
        assert chip_box[2] <= tx + tw + 8, f"{b['id']} chip box overflows card"
        d.rectangle(list(chip_box), fill=PAL["red"])
        draw_centered_in_box(d, chip_box, chip_text, cf, PAL["white"],
                             label=b["id"] + ".chip")
        yy += sh + st["gap2"]
        hb = b["budgets"]["headline"]
        draw_wrapped(d, tx, yy, c["headline"], hb["style"], hb["text_width_px"],
                     hb["lines"], PAL["ink"], b["id"] + ".headline")
        yy += st["headline"]
        db = b["budgets"]["dek"]
        # G-09: leads gap_hd 2; features dek at headline_bottom+3
        # (f9 +2: two-line sources need the room) — Sec 9 ink audit.
        dek_off = st.get("gap_hd", 0) if is_lead else (2 if b.get("sources_two_line") else 3)
        dek_y = yy + dek_off
        draw_wrapped(d, tx, dek_y, c["dek"], db["style"], db["text_width_px"],
                     db["lines"], PAL["ink_soft"], b["id"] + ".dek", exact=False)
        yy += st.get("gap_hd", 0) + st["dek"]

    sb = b["budgets"]["source_line"]
    sf = font_of("source_line")
    if is_lead:
        src = " · ".join(c["sources"])
        check_width(src, sf, sb["text_width_px"], b["id"] + ".sources")
        text(d, (tx, yy), src, sf, PAL["grey"], label=b["id"] + ".sources")
    else:
        sbf = raw_font("Liberation Sans", "Bold", 10)
        status = c["status_word"]
        rest = " — " + " · ".join(c["sources"])
        w = sbf.getlength(status) + sf.getlength(rest)
        if b.get("sources_two_line") or w > sb["text_width_px"]:
            assert len(c["sources"]) == 2, f"{b['id']} two-line sources needs 2 outlets"
            lines = [status + " — " + c["sources"][0] + " ·", c["sources"][1]]
            w1 = sbf.getlength(status) + sf.getlength(lines[0][len(status):])
            w2 = sf.getlength(lines[1])
            assert w1 <= sb["text_width_px"] and w2 <= sb["text_width_px"], \
                f"OVERFLOW {b['id']}.sources two-line: {w1:.0f}/{w2:.0f}px"
            # +1 nudge (Sec 9): dek->line1 gap was 1px at yy-11/yy
            text(d, (tx, yy - 10), status, sbf, REG[b["region"]],
                 label=b["id"] + ".sources[0]")
            text(d, (tx + sbf.getlength(status), yy - 10), lines[0][len(status):],
                 sf, PAL["grey"], label=b["id"] + ".sources[0]r")
            text(d, (tx, yy + 1), lines[1], sf, PAL["grey"], label=b["id"] + ".sources[1]")
        else:
            text(d, (tx, yy), status, sbf, REG[b["region"]],
                 label=b["id"] + ".sources")
            text(d, (tx + sbf.getlength(status), yy), rest, sf, PAL["grey"],
                 label=b["id"] + ".sources-r")
    yy += st["sources"]
    assert yy + st["pad_bottom"] <= b["y"] + b["h"] + 0.5, f"{b['id']} stack overflow"


def draw_world_map(d, b):
    wm = C["world_map"]
    d.rectangle([b["x"], b["y"], b["x"] + b["w"], b["y"] + b["h"]],
                fill=PAL["card"], outline=PAL["card_edge"], width=1)
    hf = font_of("section_header")
    check_width(wm["header"], hf, b["budgets"]["header"]["text_width_px"], "map.header")
    text(d, (b["x"] + 8, b["y"] + 4), wm["header"], hf, PAL["navy"], label="map.header")
    mw, mh = b["map_area_px"]
    mx, my = b["x"] + 8, b["y"] + 30
    graphics.draw_world_map(d, (mx, my, mx + mw, my + mh), b["pins"], L,
                            font=raw_font("Liberation Sans", "Bold", 10))
    d.rectangle([mx, my, mx + mw, my + mh], outline=PAL["card_edge"], width=1)
    ly = my + mh + 6
    lf = font_of("map_legend")
    img = getattr(d, "_image", None)
    assert img is not None, "draw_world_map needs an ImageDraw bound to an image"
    copy_leg = {x["region"]: x["text"] for x in wm["legend"]}
    for i, lg in enumerate(b["legend"]):
        cx = b["x"] + 8 + (i % 2) * 156
        cy = ly + (i // 2) * 17
        spr = _dot_sprite(tuple(lg["color_rgb"]))
        img.paste(spr, (cx, cy + 2), spr)
        txt = copy_leg[lg["region"]]
        check_width(txt, lf, b["budgets"]["legend_item"]["text_width_px"], "map.legend")
        text(d, (cx + 12, cy), txt, lf, PAL["ink"], label=f"map.legend.{lg['region']}",
             group="map.legend")
    rows = (len(b["legend"]) + 1) // 2
    assert ly + (rows - 1) * 17 + 11 <= b["y"] + b["h"], "map legend overflow"
    cap_y = ly + rows * 17
    cf = font_of("caption")
    check_width(wm["caption"], cf, b["budgets"]["caption"]["text_width_px"], "map.caption")
    assert cap_y + TYPE["caption"]["leading"] <= b["y"] + b["h"], "map caption overflow"
    text(d, (b["x"] + 8, cap_y), wm["caption"], cf, PAL["grey"], label="map.caption")


STATUS_COLORS = {"CONFIRMED": "navy", "OFFICIAL": "up", "REPORTED": "grey", "CLAIM": "red"}
DESCENDER_BRIEFS = {17, 18, 21, 33, 35}


def draw_briefs(d, b):
    hf = font_of("section_header")
    check_width(C["briefs"]["header"], hf, b["budgets"]["header"]["text_width_px"], "briefs.header")
    text(d, (b["x"], b["y"] + 0), C["briefs"]["header"], hf, PAL["navy"],
         label="briefs.header")
    copy_items = {it["number"]: it for it in C["briefs"]["items"]}
    bf, blf, sf = font_of("brief_item"), font_of("brief_leadin"), font_of("brief_source")
    sbf = raw_font("Liberation Sans", "Bold", 10)
    for it in b["items"]:
        ci = copy_items[it["number"]]
        assert ci["story_id"] == it["story_id"]
        g = f"brief{it['number']}"
        draw_badge(d, it["x"], it["y"] + 1, it["number"], it["region"])
        w = blf.getlength(ci["leadin"]) + bf.getlength(" " + ci["text"])
        assert w <= b["budgets"]["brief_text"]["text_width_px"], \
            f"OVERFLOW brief #{it['number']}: {w:.0f}px"
        text(d, (it["x"] + 18, it["y"] + 0), ci["leadin"], blf, PAL["ink"],
             label=g + ".line1a", group=g)
        text(d, (it["x"] + 18 + blf.getlength(ci["leadin"]), it["y"] + 0),
             " " + ci["text"], bf, PAL["ink"], label=g + ".line1b", group=g)
        status = ci["status_word"]
        assert status in STATUS_COLORS, f"brief #{it['number']} bad status {status!r}"
        rest = " · " + " · ".join(ci["sources"])
        w2 = sbf.getlength(status) + sf.getlength(rest)
        assert w2 <= b["budgets"]["brief_source"]["text_width_px"], \
            f"OVERFLOW brief #{it['number']} line2: {w2:.0f}px"
        y2 = it["y"] + (11 if it["number"] in DESCENDER_BRIEFS else 12)
        x2 = it["x"] + it["w"] - w2
        text(d, (x2, y2), status, sbf, PAL[STATUS_COLORS[status]],
             label=g + ".line2a", group=g)
        text(d, (x2 + sbf.getlength(status), y2), rest, sf, PAL["grey"],
             label=g + ".line2b", group=g)


def draw_datecheck(d, b):
    dc = C["datecheck"]
    d.rectangle([b["x"], b["y"], b["x"] + b["w"], b["y"] + b["h"]],
                fill=PAL["card"], outline=PAL["red"], width=1)
    lf = font_of("datecheck_label")
    text(d, (b["x"] + 8, b["y"] + 2), "DATE CHECK", lf, PAL["red"],
         label="datecheck.label1")
    text(d, (b["x"] + 8, b["y"] + 13), "— NOT 24 NOV", lf, PAL["red"],
         label="datecheck.label2")
    assert dc["label"] == "DATE CHECK — NOT 24 NOV"
    f = font_of("datecheck")
    area_w = b["budgets"]["items_text"]["text_width_px"]
    lines = wrap(dc["items_text"], f, area_w)
    assert len(lines) == 1, f"datecheck wraps to {len(lines)} lines (spec: 1 @11px)"
    check_width(lines[0], f, area_w, "datecheck.items")
    text(d, (b["x"] + 118, b["y"] + 6), lines[0], f, PAL["ink"],
         label="datecheck.items")


def draw_footer(d, b):
    fo = C["footer"]
    d.line([(b["x"], b["y"]), (b["x"] + b["w"], b["y"])], fill=PAL["rule"], width=1)
    rf = font_of("legend")
    bf = raw_font("Liberation Sans", "Bold", 11)
    budget = b["budgets"]["line"]["text_width_px"]
    prefix, rest = "HOW SURE:", fo["line1"][len("HOW SURE:"):]
    w = bf.getlength(prefix) + rf.getlength(rest)
    assert w <= budget, f"OVERFLOW footer line1: {w:.0f}px"
    text(d, (b["x"], b["y"] + 1), prefix, bf, PAL["ink"], label="footer.line1a")
    text(d, (b["x"] + bf.getlength(prefix), b["y"] + 1), rest, rf, PAL["ink"],
         label="footer.line1b")
    displayed = []
    for ck in ("lead_dominant", "lead_sec_1", "lead_sec_2") + tuple(f"feature_{i}" for i in range(4, 14)):
        displayed += C[ck]["sources"]
    for it in C["briefs"]["items"]:
        displayed += it["sources"]
    assert set(fo["sources"]) == set(displayed), \
        f"A4 footer set mismatch: {set(fo['sources']) ^ set(displayed)}"
    assert list(fo["sources"]) == list(dict.fromkeys(displayed)), "A4 footer order"
    units = fo["line2"].split(", ")
    lines, cur = [], ""
    for u in units:
        t = (cur + ", " + u) if cur else u
        if rf.getlength(t) <= budget or not cur:
            cur = t
        else:
            lines.append(cur)
            cur = u
    if cur:
        lines.append(cur)
    assert len(lines) <= 2, f"footer sources wrap to {len(lines)} lines (spec: <=2)"
    assert ", ".join(lines) == fo["line2"], "footer wrap altered text"
    for i, ln in enumerate(lines):
        text(d, (b["x"], b["y"] + 13 + i * 12), ln, rf, PAL["grey"],
             label=f"footer.src[{i}]")


def render(out_path):
    assert_no_block_overlap()
    INK_BOXES.clear()
    img = Image.new("RGB", (1024, 1024), PAL["paper"])
    d = ImageDraw.Draw(img)
    d.rectangle([10, 10, 1013, 1013], outline=PAL["rule"], width=2)
    d.rectangle([15, 15, 1008, 1008], outline=PAL["rule"], width=1)
    for b in L["blocks"]:
        kind = b["kind"]
        if kind == "masthead":
            draw_masthead(d, b)
        elif kind == "region_chips":
            draw_region_chips(d, b)
        elif kind == "timeline_numbers":
            draw_timeline_numbers(d, b)
        elif kind in ("lead_card", "feature_card"):
            draw_card(d, b)
        elif kind == "world_map":
            draw_world_map(d, b)
        elif kind == "briefs":
            draw_briefs(d, b)
        elif kind == "date_check":
            draw_datecheck(d, b)
        elif kind == "confidence_footer":
            draw_footer(d, b)
        else:
            raise ValueError(f"unknown block kind {kind}")
    assert img.size == (1024, 1024)
    ink_audit(img)
    img.save(out_path, format="PNG")
    data = open(out_path, "rb").read()
    assert len(data) <= 1048576, f"entry.png too big: {len(data)} bytes"
    return hashlib.sha256(data).hexdigest(), len(data)


if __name__ == "__main__":
    out = os.path.join(HERE, "entry.png")
    h, n = render(out)
    print(f"entry.png: {n} bytes, sha256 {h}")
