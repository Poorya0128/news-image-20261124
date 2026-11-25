#!/usr/bin/env python3
"""A12: build layout.json for v3 port (v2 content on 1cec3843 design).

Starts from layout_1cec3843.json; applies v3_port_spec_a10.md Sec 1-8:
Sec 2 block stack, Sec 3 type scale (datecheck 11px; delete brief_code /
briefs_legend), Sec 2 story numbering/regions, Sec 7.1 pins (12, pin10
Mongbwalu), Sec 7.2 briefs (22, col-major 11+11, pitch 22).
"""
import copy
import json
import os
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
L = json.load(open(os.path.join(HERE, "layout_1cec3843.json")))
C = json.load(open(os.path.join(HERE, "copy.json")))

# --- Sec 3 type scale: datecheck 12->11 (leading 13); delete brief_code/briefs_legend
L["type_scale"]["datecheck"] = {"family": "Liberation Sans", "weight": "Regular",
                                "size": 11, "leading": 13}
L["type_scale"].pop("brief_code", None)
L["type_scale"].pop("briefs_legend", None)

blocks = {b["id"]: b for b in L["blocks"]}

# --- Sec 2 block stack (x, y, w, h)
GEOM = {
    "masthead": (20, 16, 984, 73),
    "region_chips": (20, 101, 984, 20),
    "timeline_numbers": (20, 133, 984, 47),
    "lead_1": (20, 192, 320, 187),
    "lead_2": (352, 192, 320, 187),
    "lead_3": (684, 192, 320, 187),
    "feature_4": (20, 391, 188, 124),
    "feature_5": (220, 391, 188, 124),
    "feature_6": (420, 391, 188, 124),
    "feature_7": (620, 391, 188, 124),
    "feature_8": (820, 391, 184, 124),
    "feature_9": (20, 527, 188, 124),
    "feature_10": (220, 527, 188, 124),
    "feature_11": (420, 527, 188, 124),
    "feature_12": (620, 527, 188, 124),
    "feature_13": (820, 527, 184, 124),
    "world_map": (20, 663, 320, 258),
    "briefs": (352, 663, 652, 258),
    "datecheck": (20, 933, 984, 24),
    "footer": (20, 969, 984, 39),
}
for bid, (x, y, w, h) in GEOM.items():
    b = blocks[bid]
    b["x"], b["y"], b["w"], b["h"] = x, y, w, h

# --- copy keys: leads renamed in v2 copy.json
COPY_KEY = {"lead_1": "lead_dominant", "lead_2": "lead_sec_1", "lead_3": "lead_sec_2"}
for bid, ck in COPY_KEY.items():
    blocks[bid]["copy_key"] = ck
for i in range(4, 14):
    blocks[f"feature_{i}"]["copy_key"] = f"feature_{i}"

# --- Sec 2 regions per story number
REGION_BY_NUM = {
    1: "Middle East", 2: "North America", 3: "East Asia", 4: "Global",
    5: "North America", 6: "South & SE Asia", 7: "East Asia", 8: "Middle East",
    9: "Middle East", 10: "Africa", 11: "Europe", 12: "Europe", 13: "East Asia",
    14: "Europe", 15: "Europe", 16: "Europe", 17: "Middle East", 18: "Middle East",
    19: "Africa", 20: "South & SE Asia", 21: "East Asia", 22: "South & SE Asia",
    23: "South & SE Asia", 24: "South & SE Asia", 25: "South America", 26: "Europe",
    27: "Middle East", 28: "South & SE Asia", 29: "North America", 30: "South America",
    31: "Middle East", 32: "East Asia", 33: "Oceania", 34: "Middle East",
    35: "North America",
}
# recount assert vs copy chips (Sec 2 / G-07)
counts = Counter(REGION_BY_NUM.values())
assert len(counts) == 9 and sum(counts.values()) == 35, counts
for ch in C["region_chips"]["chips"]:
    assert counts[ch["region"]] == ch["count"], (ch, counts)

# --- masthead: claim line = v2 string
blocks["masthead"]["budgets"]["claim_line"]["text"] = C["masthead"]["claim_line"]

# --- region chips: v2 counts/texts, colours from region_colors
rc = L["region_colors"]
blocks["region_chips"]["chips"] = [
    {"region": ch["region"], "count": ch["count"],
     "color_rgb": list(rc[ch["region"]]["rgb"]), "text": ch["text"]}
    for ch in C["region_chips"]["chips"]
]

# --- timeline pins: v2's 5 (15:42 Riyadh + 18:06 SF removed)
tl = blocks["timeline_numbers"]
tl["pins"] = [{"utc": p["utc"], "label": p["label"], "story_id": p["story_id"]}
              for p in C["timeline"]["pins"]]
assert len(tl["pins"]) == 5
tl["numbers"]["note"] = ("figures + captions in copy.json numbers_strip; "
                         "numeral at (cell_x+10, y+18), caption at (cell_x+10, y+38) "
                         "(Sec 9 nudge from spec y+19/y+36)")

# --- leads: Sec 6.1 stack (scene 76, gap_hd 2, pad_bottom 2)
for bid in ("lead_1", "lead_2", "lead_3"):
    b = blocks[bid]
    ck = COPY_KEY[bid]
    c = C[ck]
    assert b["story_id"] == c["story_id"] and b["number"] == c["number"]
    assert b["region"] == REGION_BY_NUM[c["number"]]
    b["stack_px"] = {"pad_top": 4, "kicker_row": 13, "gap1": 2, "scene": 76,
                     "gap2": 3, "headline": 48, "gap_hd": 2, "dek": 26,
                     "sources": 11, "pad_bottom": 2}
    assert sum(b["stack_px"].values()) == 187
    b["scene_area_px"] = [300, 76]
    b["status_tag"] = c["status_word"]
    b["number_chip"] = c["badge"]
    b["kicker_ref"] = c["kicker"]
    b["sources_display"] = list(c["sources"])
    b["budgets"]["kicker"]["text_ref"] = c["kicker"]
    b["budgets"]["number_chip"]["text"] = c["badge"]

# --- features: Sec 6.2/6.3 stacks. NOTE: spec text lists headline 36 +
# dek 26 but 4+13+2+30+2+36+26+11+2 = 126 != 124. True-ink audit
# (Sec 9) also shows headline->dek needs 38-39px draw distance.
# Resolution: headline slot 36, dek slot 24 (all deks 1 line), dek drawn
# at headline_bottom+3 (f9: +2, two-line sources). Sum = 124.
for i in range(4, 14):
    bid = f"feature_{i}"
    b = blocks[bid]
    c = C[bid]
    assert b["story_id"] == c["story_id"] and b["number"] == c["number"], bid
    assert b["region"] == REGION_BY_NUM[c["number"]], bid
    b["status_tag"] = c["status_word"]
    b["kicker_ref"] = c["kicker"]
    b["sources_display"] = list(c["sources"])
    b["budgets"]["kicker"]["text_ref"] = c["kicker"]
    if b.get("variant") == "markets_table":
        b["stack_px"] = {"pad_top": 4, "kicker_row": 13, "gap1": 2,
                         "headline": 18, "gap2": 2, "table_6_rows": 72,
                         "sources": 11, "pad_bottom": 2}
        assert sum(b["stack_px"].values()) == 124
        b.pop("number_chip", None)
        b["budgets"].pop("number_chip", None)
        b["budgets"]["table_rows"]["instruments"] = [r["instrument"] for r in c["table_rows"]]
    else:
        b["stack_px"] = {"pad_top": 4, "kicker_row": 13, "gap1": 2, "scene": 30,
                         "gap2": 2, "headline": 36, "dek": 24, "sources": 11,
                         "pad_bottom": 2}
        assert sum(b["stack_px"].values()) == 124
        b["scene_area_px"] = [172 if b["w"] == 188 else 168, 30]
        b["number_chip"] = c["badge"]
        b["budgets"]["number_chip"]["text"] = c["badge"]
        # chip font step-down (Sec 6.2 + A7 sign-off); render re-measures
        b["chip_font_px"] = {5: 13, 6: 12, 7: 11, 8: 11, 9: 13, 10: 13,
                             11: 13, 12: 13, 13: 9}[i]
    # f9 two-line sources (Sec 6.2); f5 fallback handled render-side (R-2)
    if i == 9:
        b["sources_two_line"] = True

# --- world map: Sec 7.1 pins (12; pin 4 dropped; pin 10 Mongbwalu)
wm = blocks["world_map"]
wm["map_area_px"] = [304, 112]
PINS = [  # (number, story_id, lon, lat)
    (1, "a4-01", 46.68, 24.71), (2, "a6-04", -73.99, 40.69),
    (3, "gap-01", 121.47, 31.23), (5, "a6-02", -122.42, 37.77),
    (6, "a5-03", 101.69, 3.14), (7, "a5-01", 116.40, 39.90),
    (8, "a4-03", 51.42, 35.69), (9, "a4-05", 34.47, 31.50),
    (10, "a6-07", 30.046, 1.935), (11, "gap-04", 35.14, 47.84),
    (12, "gap-02", 2.35, 48.86), (13, "a6-06", 100.29, 40.96),
]
wm["pins"] = [{"number": n, "story_id": s, "lon": lon, "lat": lat}
              for n, s, lon, lat in PINS]
assert len(wm["pins"]) == 12 and all(p["number"] != 4 for p in wm["pins"])
p10 = [p for p in wm["pins"] if p["number"] == 10][0]
assert (p10["lon"], p10["lat"]) == (30.046, 1.935), p10
# legend: 9 regions, colours; counts updated (render shows names only, B3)
wm["legend"] = [{"region": ch["region"], "count": ch["count"],
                 "color_rgb": list(rc[ch["region"]]["rgb"])}
                for ch in C["region_chips"]["chips"]]
# card map_pin refs: keep consistent (pin 4 card keeps no pin)
for bid in ("lead_1", "lead_2", "lead_3") + tuple(f"feature_{i}" for i in range(4, 14)):
    b = blocks[bid]
    pin = next((p for p in wm["pins"] if p["number"] == b["number"]), None)
    if pin:
        b["map_pin"] = {"number": pin["number"], "lon": pin["lon"], "lat": pin["lat"]}
    else:
        b.pop("map_pin", None)

# --- briefs: Sec 7.2 two-line pitch 22, col-major 11+11
br = blocks["briefs"]
br["budgets"] = {
    "header": {"style": "section_header", "text_width_px": 636, "lines": 1},
    "brief_text": {"style": "brief_item", "text_width_px": 302, "lines": 1,
                   "note": "line 1: leadin Bold + text Regular at col_x+18"},
    "brief_source": {"style": "brief_source", "text_width_px": 302, "lines": 1,
                     "note": "line 2: status WORD Bold 10 (status colour) + ' · ' + sources, right-aligned"},
}
items = []
for idx, ci in enumerate(C["briefs"]["items"]):
    col = 0 if idx < 11 else 1
    row = idx if idx < 11 else idx - 11
    items.append({
        "number": ci["number"], "story_id": ci["story_id"],
        "col": col, "row": row,
        "x": 352 + col * 332, "y": 663 + 15 + row * 22, "w": 320,
        "pitch_px": 22, "status_word": ci["status_word"],
        "region": REGION_BY_NUM[ci["number"]],
        "sources_display": list(ci["sources"]),
    })
assert len(items) == 22
br["items"] = items

# --- datecheck: Sec 8.1 (5 v2 items, 1 line @11px, budget 858)
dc = blocks["datecheck"]
dc["items"] = copy.deepcopy(C["datecheck"]["items"])
dc.pop("reserve_items", None)
dc["budgets"]["items_text"] = {"style": "datecheck", "text_width_px": 858,
                               "lines": 1}
dc["rendered_text_ref"] = C["datecheck"]["items_text"]

# --- footer: Sec 8.2 (28 outlets, auto; render asserts set equality)
fo = blocks["footer"]
fo["sources_list"] = list(C["footer"]["sources"])
assert len(fo["sources_list"]) == 28
fo["legend_text"] = C["footer"]["line1"]
fo.pop("note_text", None)

L["meta"] = {
    "phase": "v3 port (v2 content on 1cec3843 design)",
    "spec": "v3_port_spec_a10.md",
    "stories": 35, "regions": 9,
    "region_counts": dict(counts),
    "note": "geometry per spec Sec 2; feature dek slot 24 + dek offset +3/+2 (Sec 9 ink audit, see make_layout_v3.py)",
}

with open(os.path.join(HERE, "layout.json"), "w", encoding="utf-8") as f:
    json.dump(L, f, indent=2, ensure_ascii=False)
print(f"layout.json written: {len(L['blocks'])} blocks, counts {dict(counts)}")
