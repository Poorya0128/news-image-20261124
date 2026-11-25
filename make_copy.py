#!/usr/bin/env python3
"""A9 Copy Editor: writes copy.json (v3 port build).

v2 CONTENT on the 1cec3843 (old) design geometry, per v3_port_spec_a10.md
(user redirection 2026-11-25: v2 content onto the previous design). v2
content rulings stand in full:
- 35 stories (A7 final list: 9 cuts, 6 additions a3-09/a4-12/a5-09/a5-15/
  a4-14/a3-07). Claim: "35 DATED STORIES · 9 REGIONS · ALL FROM TUE 24 NOV
  2026" (no FIELDS, D7).
- Certainty IN WORDS everywhere (A2 order): CONFIRMED/OFFICIAL/REPORTED/CLAIM
  per A7 Sec 6 assignments (16/17/0/2). CONFIRMED displays two outlets.
  Leads (old format): status word in top-right tag, sources " · ".join.
  Features: sources line "STATUS — A · B" (feature_9 wraps to 2 lines at
  the outlet boundary). Briefs two-line: line 2 = certainty word + sources.
  No circled letters, no header legend; one legend in footer only.
- A1 date integrity: no visible non-24-Nov date in any story (DATE CHECK
  excepted). Sparta II brief + Gaza meningitis deleted; Indonesia rewritten
  as 24 Nov probe/toll event; Gavi dek without WHO toll; Riyadh dek without
  "19 November".
- A3 sources per A7 Sec 3 (banned displays replaced or story dropped).
- A5: Huawei dek = A7-approved verbatim (v2_micro_a7.md R-1); field COURTS;
  badge "1ST FOREIGN ASTRONAUT" (A5-literal, never shortened).
- D2 strip: 6 NEW numbers (A7 Sec 5), none stated elsewhere on the page.
- D4 briefs self-explanatory; D5 uniform style; D6 DATE CHECK 5 items.
- A4 footer sources generated programmatically from displayed set (asserted).
- Badges (C4): max 1/card, never repeat headline number. v3 chip focal
  clearance shortenings (spec Sec 6.2): f6 "RETURNS IN DEC", f7 "PAUSED TO
  27 JAN", f8 "GHALIBAF SPEAKS", f10 "BUNDIBUGYO" — A7 sign-off pending.
- f9 dek comma form "Naeem Abu Nahel, six others" (spec Sec 6.2) — A7
  sign-off pending (spec R-1).
- Timeline: 5 pins; Riyadh 15:42 pin removed (A7: false time).
- R-7 (for A12/layout): map pin 10 = Mongbwalu, Ituri Province,
  lat 1.935, lon 30.046 (WHO DON630/ECDC/Science via A7 micro-confirmation).
  Never 0.5,29.5 (North Kivu, wrong) and never Kinshasa.
"""
import json
import re
from collections import Counter

NBSP = "\u00a0"

copy = {
    "meta": {
        "owner": "A9 Chief Copy Editor & Headline Writer",
        "phase": "v3 port build (v2 content on 1cec3843 design, 35 stories, certainty in words)",
        "date_exact": "Tuesday 24 November 2026",
        "notes": [
            "Every string verified against v3_port_spec_a10.md budgets (glyph width) by check_copy.py.",
            "Facts/sources/certainty per v2_verification_a7.md (A7/A8); Huawei dek verbatim per v2_micro_a7.md R-1.",
            "R-7 FOR A12 (layout): map pin 10 (a6-07 Congo) = Mongbwalu, Ituri Province, lat 1.935, lon 30.046. Never 0.5,29.5, never Kinshasa.",
            "Certainty in words on every item (A7 Sec 6: 16 CONFIRMED / 17 OFFICIAL / 0 REPORTED / 2 CLAIM); CONFIRMED displays two outlets.",
            "Footer sources generated from displayed set in make_copy.py (A4 equality asserted) = 28 outlets incl. USGS (displayed for a5-07 per A7 certainty table); A7 sign-off (v2_signoff_a7.md §1): 28 stands.",
            "Display-name shortenings (A7-approved): 'JoongAng Daily' (Korea JoongAng Daily), 'Dept of Industry' (Department of Industry). Footer uses displayed forms (equality).",
            "Chen badge: A1 ruling — '4TH SINCE 2025' (A7-approved, v2_signoff_a7.md §3).",
            "Numbers strip: 6 NEW figures (A7 Sec 5), none printed elsewhere; Gavi dek does not print $40m; Venezuela caption does not print end-2025.",
            "DATE CHECK: 5 items (D6), NBSP-bound dates so wrap never splits a date.",
            "v3 port (v3_port_spec_a10.md): v2 content on 1cec3843 design. Leads: status word in tag, sources ' · '.join. Features: sources 'STATUS — A · B' (feature_9 two-line wrap at outlet boundary). Briefs two-line pitch 22, 2 cols.",
            "Badge shortenings for chip focal clearance (spec Sec 6.2) — A7 SIGN-OFF PENDING: f6 'RETURNS IN DEC' (pure abbreviation of December), f7 'PAUSED TO 27 JAN' (year dropped — spec: A7 call), f8 'GHALIBAF SPEAKS' (venue 'parliament' dropped), f10 'BUNDIBUGYO' ('VACCINE' dropped). f13 badge '1ST FOREIGN ASTRONAUT' unchanged (A5-literal; A1 ruling: chip @9px + rocket shift).",
            "f9 dek 'Naeem Abu Nahel, six others' (comma form, 155.4px 1 line, spec Sec 6.2) — A7 SIGN-OFF PENDING (spec R-1).",
        ],
    },
    "masthead": {
        "kicker": "THE WORLD IN ONE DAY",
        "date": "Tuesday 24 November 2026",
        "claim_line": "35 DATED STORIES · 9 REGIONS · ALL FROM TUE 24 NOV 2026",
        "subhead": "Houthi drone hits Riyadh tower · Huawei found guilty in US · Shanghai chief under probe",
    },
    "region_chips": {
        "chips": [
            {"region": "Europe", "count": 6, "text": "EUROPE 6"},
            {"region": "Middle East", "count": 8, "text": "MIDDLE EAST 8"},
            {"region": "South & SE Asia", "count": 6, "text": "SOUTH & SE ASIA 6"},
            {"region": "East Asia", "count": 5, "text": "EAST ASIA 5"},
            {"region": "North America", "count": 4, "text": "NORTH AMERICA 4"},
            {"region": "Africa", "count": 2, "text": "AFRICA 2"},
            {"region": "Global", "count": 1, "text": "GLOBAL 1"},
            {"region": "Oceania", "count": 1, "text": "OCEANIA 1"},
            {"region": "South America", "count": 2, "text": "SOUTH AMERICA 2"},
        ]
    },
    "timeline": {
        "pins": [
            {"utc": "01:00", "label": "Hanoi blast", "story_id": "a5-06"},
            {"utc": "01:32", "label": "Nepal quake", "story_id": "a5-07"},
            {"utc": "10:16", "label": "Iran 7 conditions", "story_id": "a4-03"},
            {"utc": "13:00", "label": "Cartagena siege", "story_id": "a3-04"},
            {"utc": "21:00", "label": "US markets close", "story_id": "a6-01"},
        ],
        "strip_text": "TUESDAY UTC — 01:00 Hanoi blast · 01:32 Nepal quake · 10:16 Iran 7 conditions · 13:00 Cartagena siege · 21:00 US markets close",
    },
    "numbers_strip": {
        "label": ["THE DAY", "IN NUMBERS"],
        "figures": [
            {"numeral": "364,000", "caption": "Yemen displaced since August", "story_id": "a4-12"},
            {"numeral": "$81.91", "caption": "Anthropic close vs $83 IPO", "story_id": "a6-03"},
            {"numeral": "$40m", "caption": "Gavi Ebola vaccine fund", "story_id": "a6-07"},
            {"numeral": "242%", "caption": "Venezuela debt vs GDP", "story_id": "a3-09"},
            {"numeral": "32.9%", "caption": "SA jobless rate (IMF)", "story_id": "a4-13"},
            {"numeral": "$82.05", "caption": "WTI crude settlement", "story_id": "a6-01"},
        ],
    },
    "lead_dominant": {
        "story_id": "a4-01", "number": 1,
        "kicker": "RIYADH · WAR",
        "status_word": "CONFIRMED",
        "badge": "2ND STRIKE IN A WEEK",
        "headline": "Houthi drone hits Riyadh tower, wounds 11",
        "dek": "Second strike on the PIF Tower in under a week, in the Saudi capital's financial district.",
        "sources": ["Reuters", "WSJ"],
        "source_line": "Reuters · WSJ",
    },
    "lead_sec_1": {
        "story_id": "a6-04", "number": 2,
        "kicker": "BROOKLYN · COURTS",
        "status_word": "OFFICIAL",
        "badge": "GUILTY 10 OF 12",
        "headline": "Huawei convicted in US over Iran business",
        "dek": "Cleared: racketeering, obstruction; sentencing 14 Sep 2027",
        "sources": ["Reuters", "WSJ"],
        "source_line": "Reuters · WSJ",
    },
    "lead_sec_2": {
        "story_id": "gap-01", "number": 3,
        "kicker": "SHANGHAI · POLITICS",
        "status_word": "OFFICIAL",
        "badge": "4TH SINCE 2025",
        "headline": "China probes Shanghai chief Chen Jining",
        "dek": "The 62-year-old faces a CCDI corruption investigation",
        "sources": ["Reuters", "CNN"],
        "source_line": "Reuters · CNN",
    },
    "feature_4": {
        "story_id": "a6-01", "number": 4,
        "kicker": "GLOBAL · MARKETS",
        "status_word": "CONFIRMED",
        "headline": "Dow back above 50,000",
        "table_rows": [
            {"instrument": "Dow Jones", "value": "50,018.70", "change": "+0.85%"},
            {"instrument": "S&P 500", "value": "7,201.09", "change": "-0.50%"},
            {"instrument": "Nasdaq", "value": "23,733.54", "change": "-1.48%"},
            {"instrument": "Nikkei 225", "value": "58,644.63", "change": "+3.91%"},
            {"instrument": "Brent crude", "value": "$91.40", "change": "+2.27%"},
            {"instrument": "Gold Dec-26", "value": "$3,561.90", "change": "-2.45%"},
        ],
        "sources": ["AP", "WSJ"],
        "source_line": "AP · WSJ",
    },
    "feature_5": {
        "story_id": "a6-02", "number": 5,
        "kicker": "CALIFORNIA · TECH",
        "status_word": "CONFIRMED",
        "badge": "CHIP INDEX -7.88%",
        "headline": "Nvidia falls 5.9% as rally unwinds",
        "dek": "Close $155.38, down 5.86%",
        "sources": ["Reuters", "Motley Fool"],
        "source_line": "Reuters · Motley Fool",
    },
    "feature_6": {
        "story_id": "a5-03", "number": 6,
        "kicker": "MALAYSIA · POLITICS",
        "status_word": "OFFICIAL",
        "badge": "RETURNS IN DEC",
        "headline": "Myanmar nationals: 6,803 to return",
        "dek": "AFP: most are Rohingya",
        "sources": ["AP", "AFP"],
        "source_line": "AP · AFP",
    },
    "feature_7": {
        "story_id": "a5-01", "number": 7,
        "kicker": "BEIJING · TRADE",
        "status_word": "OFFICIAL",
        "badge": "PAUSED TO 27 JAN",
        "headline": "China extends US export-control pause",
        "dek": "Gallium, germanium, antimony",
        "sources": ["Reuters", "Xinhua"],
        "source_line": "Reuters · Xinhua",
    },
    "feature_8": {
        "story_id": "a4-03", "number": 8,
        "kicker": "TEHRAN · DIPLOMACY",
        "status_word": "OFFICIAL",
        "badge": "GHALIBAF SPEAKS",
        "headline": "Iran: no US talks until 7 conditions met",
        "dek": "Sanctions lift, frozen assets",
        "sources": ["AP", "Argus Media"],
        "source_line": "AP · Argus Media",
    },
    "feature_9": {
        "story_id": "a4-05", "number": 9,
        "kicker": "GAZA · WAR",
        "status_word": "CONFIRMED",
        "badge": "7 KILLED",
        "headline": "Israeli strike kills Hamas security chief",
        "dek": "Naeem Abu Nahel, six others",
        "sources": ["Reuters", "Times of Israel"],
        "source_line": "Reuters · Times of Israel",
    },
    "feature_10": {
        "story_id": "a6-07", "number": 10,
        "kicker": "CONGO · HEALTH",
        "status_word": "OFFICIAL",
        "badge": "BUNDIBUGYO",
        "headline": "Gavi secures up to 1.5m Ebola doses",
        "dek": "Conditional on trial results.",
        "sources": ["Reuters", "Gavi"],
        "source_line": "Reuters · Gavi",
    },
    "feature_11": {
        "story_id": "gap-04", "number": 11,
        "kicker": "ZAPORIZHZHIA · WAR",
        "status_word": "CONFIRMED",
        "badge": "48 WOUNDED",
        "headline": "Russian strike kills 2 in Zaporizhzhia",
        "dek": "4 children among the wounded",
        "sources": ["Reuters", "AP"],
        "source_line": "Reuters · AP",
    },
    "feature_12": {
        "story_id": "gap-02", "number": 12,
        "kicker": "PARIS · BUSINESS",
        "status_word": "OFFICIAL",
        "badge": "$175 A SHARE",
        "headline": "Sanofi to buy Insmed for $41bn",
        "dek": "Close expected in H1 2027",
        "sources": ["WSJ", "Sanofi"],
        "source_line": "WSJ · Sanofi",
    },
    "feature_13": {
        "story_id": "a6-06", "number": 13,
        "kicker": "CHINA · SPACE",
        "status_word": "OFFICIAL",
        "badge": "1ST FOREIGN ASTRONAUT",
        "headline": "First foreign astronaut joins China crew",
        "dek": "Pakistani pilot unveiled",
        "sources": ["Reuters", "AP"],
        "source_line": "Reuters · AP",
    },
    "world_map": {
        "header": "WHERE IT HAPPENED",
        "legend": [
            {"region": "Europe", "text": "Europe"},
            {"region": "Middle East", "text": "Middle East"},
            {"region": "South & SE Asia", "text": "South & SE Asia"},
            {"region": "East Asia", "text": "East Asia"},
            {"region": "North America", "text": "North America"},
            {"region": "Africa", "text": "Africa"},
            {"region": "Global", "text": "Global"},
            {"region": "Oceania", "text": "Oceania"},
            {"region": "South America", "text": "South America"},
        ],
        "caption": "Pins = numbered stories above",
    },
    "briefs": {
        "header": "ALSO ON TUESDAY — 22 MORE STORIES",
        "items": [
            {"number": 14, "story_id": "a3-02", "leadin": "Poland:", "text": "drone overnight into Tuesday", "status_word": "OFFICIAL", "sources": ["Fox News"]},
            {"number": 15, "story_id": "a3-05", "leadin": "UK", "text": "warns Ukraine suppliers: sabotage", "status_word": "OFFICIAL", "sources": ["Reuters", "The Times"]},
            {"number": 16, "story_id": "a3-06", "leadin": "France:", "text": "Sarkozy to stand trial", "status_word": "OFFICIAL", "sources": ["Le Monde"]},
            {"number": 17, "story_id": "a4-04", "leadin": "Iran", "text": "says ship hit mine off Khasab", "status_word": "CLAIM", "sources": ["Middle East Eye"]},
            {"number": 18, "story_id": "a4-10", "leadin": "Turkey", "text": "helicopter crash kills five", "status_word": "CONFIRMED", "sources": ["Reuters", "Aviation Today"]},
            {"number": 19, "story_id": "a4-13", "leadin": "IMF:", "text": "South Africa growth 1.0%", "status_word": "OFFICIAL", "sources": ["IMF"]},
            {"number": 20, "story_id": "a5-04", "leadin": "Hasina", "text": "plans return on 16 Dec", "status_word": "CONFIRMED", "sources": ["Reuters", "AP"]},
            {"number": 21, "story_id": "a5-10", "leadin": "Seoul", "text": "to return North Korean boat", "status_word": "CONFIRMED", "sources": ["Yonhap", "JoongAng Daily"]},
            {"number": 22, "story_id": "a5-06", "leadin": "01:00 Hanoi", "text": "eatery blast kills six", "status_word": "CONFIRMED", "sources": ["Reuters", "AP"]},
            {"number": 23, "story_id": "a5-07", "leadin": "01:32 Nepal", "text": "quake mag. 5.3 (USGS)", "status_word": "CONFIRMED", "sources": ["Reuters", "USGS"]},
            {"number": 24, "story_id": "a5-11", "leadin": "Pakistan", "text": "raids kill 8 suspected", "status_word": "CLAIM", "sources": ["Xinhua"]},
            {"number": 25, "story_id": "a3-04", "leadin": "13:00 Cartagena", "text": "25 hostages still held", "status_word": "CONFIRMED", "sources": ["Reuters", "iHeart"]},
            {"number": 26, "story_id": "a6-09", "leadin": "Madrid", "text": "5-1 PSV; City, Arsenal held", "status_word": "OFFICIAL", "sources": ["UEFA", "Reuters"]},
            {"number": 27, "story_id": "a4-02", "leadin": "Houthis", "text": "60 km from Aden, army says", "status_word": "CONFIRMED", "sources": ["Reuters", "AFP"]},
            {"number": 28, "story_id": "a5-05", "leadin": "Indonesia", "text": "probes factory fire; toll 26", "status_word": "CONFIRMED", "sources": ["AP", "Xinhua"]},
            {"number": 29, "story_id": "a6-03", "leadin": "Anthropic", "text": "slips below IPO price", "status_word": "CONFIRMED", "sources": ["Reuters", "MarketWatch"]},
            {"number": 30, "story_id": "a3-09", "leadin": "Venezuela", "text": "puts debt at $237.5bn", "status_word": "CONFIRMED", "sources": ["Reuters", "WSJ"]},
            {"number": 31, "story_id": "a4-12", "leadin": "UN:", "text": "350,000 in Taiz missed shots", "status_word": "OFFICIAL", "sources": ["UN News", "Arab News"]},
            {"number": 32, "story_id": "a5-09", "leadin": "North Korea", "text": "threatens Swiss office", "status_word": "OFFICIAL", "sources": ["Reuters"]},
            {"number": 33, "story_id": "a5-15", "leadin": "Australia", "text": "PM's science prize shared", "status_word": "OFFICIAL", "sources": ["Dept of Industry", "pm.gov.au"]},
            {"number": 34, "story_id": "a4-14", "leadin": "Baghdad", "text": "orders Kurdish oil control", "status_word": "OFFICIAL", "sources": ["Reuters"]},
            {"number": 35, "story_id": "a3-07", "leadin": "Trump", "text": "awards Giuliani top medal", "status_word": "CONFIRMED", "sources": ["Reuters", "USA Today"]},
        ],
    },
    "datecheck": {
        "label": "DATE CHECK — NOT 24 NOV",
        "items": [
            {"story": "Russian corvette Merkury sunk at Benghazi", "true_date": "Sun 22 Nov", "short_label": "Merkury sunk"},
            {"story": "Ukraine drone strike on Sparta II (the strike itself)", "true_date": "Sat 21 Nov", "short_label": "Sparta II strike"},
            {"story": "Iran flogs singer Parastoo Ahmadi (74 lashes)", "true_date": "Mon 23 Nov", "short_label": "Ahmadi flogged"},
            {"story": "WFP chief: wars could add $727m in costs", "true_date": "Mon 23 Nov", "short_label": "WFP cost warning"},
            {"story": "Shenzhou-24 launch (only the 24 Nov crew unveiling is on this page)", "true_date": "Wed 25 Nov", "short_label": "Shenzhou-24 launch"},
        ],
        "items_text": " · ".join(
            f"{lab} — {d.replace(' ', NBSP)}" for lab, d in [
                ("Merkury sunk", "Sun 22 Nov"),
                ("Sparta II strike", "Sat 21 Nov"),
                ("Ahmadi flogged", "Mon 23 Nov"),
                ("WFP cost warning", "Mon 23 Nov"),
                ("Shenzhou-24 launch", "Wed 25 Nov"),
            ]
        ),
    },
    "footer": {
        "line1": "HOW SURE: CONFIRMED = 2+ outlets · OFFICIAL = on record · REPORTED = single wire · CLAIM = one side's account",
        # line2 + sources generated below (A4)
    },
}

# Compose brief full_text / label_line
for _it in copy["briefs"]["items"]:
    _it["full_text"] = _it["leadin"] + " " + _it["text"]
    _it["label_line"] = _it["status_word"] + " · " + " · ".join(_it["sources"])

# Compose card sources lines (v3 port formats, spec Sec 6.1/6.2):
# leads: " · ".join(sources) (status word in the top-right tag, old format);
# features: "STATUS — A · B" (status Bold 10 + " — " + sources Regular 10);
# feature_9 wraps to 2 lines at the outlet boundary (185.0 > 172px).
_TWO_LINE = {"feature_9"}
_LEADS = ["lead_dominant", "lead_sec_1", "lead_sec_2"]
for _k in _LEADS + [f"feature_{i}" for i in range(4, 14)]:
    _c = copy[_k]
    assert _c["source_line"] == " · ".join(_c["sources"]), f"{_k}: source_line literal drift"
    if _k in _LEADS:
        _c["source_lines"] = [_c["source_line"]]
    else:
        _c["source_line"] = _c["status_word"] + " — " + " · ".join(_c["sources"])
        if _k in _TWO_LINE:
            _c["source_lines"] = [_c["status_word"] + " — " + _c["sources"][0] + " ·", _c["sources"][1]]
        else:
            _c["source_lines"] = [_c["source_line"]]

# --- A4 footer: generate sources from displayed set, first-appearance order ---
_PAGE_ORDER = ["lead_dominant", "lead_sec_1", "lead_sec_2"] + [f"feature_{i}" for i in range(4, 14)]
_displayed = []
for _k in _PAGE_ORDER:
    _displayed += copy[_k]["sources"]
for _it in copy["briefs"]["items"]:
    _displayed += _it["sources"]
_footer_sources = list(dict.fromkeys(_displayed))
assert set(_footer_sources) == set(_displayed), "footer set != displayed set"
copy["footer"]["sources"] = _footer_sources
copy["footer"]["line2"] = "Sources: " + ", ".join(_footer_sources)

# --- Guards ---
DISPLAY_REGION = {
    "Europe": "Europe", "Middle East": "Middle East", "Africa": "Africa",
    "East Asia (China)": "East Asia", "East Asia (North Korea)": "East Asia",
    "East Asia (South Korea/North Korea)": "East Asia",
    "East Asia (Japan)": "East Asia", "Asia-Pacific": "East Asia",
    "Southeast Asia (Malaysia/Myanmar)": "South & SE Asia",
    "Southeast Asia (Indonesia)": "South & SE Asia",
    "Southeast Asia (Vietnam)": "South & SE Asia",
    "Southeast Asia (Philippines)": "South & SE Asia",
    "South Asia (Bangladesh)": "South & SE Asia",
    "South Asia (Nepal)": "South & SE Asia",
    "South Asia (Pakistan)": "South & SE Asia",
    "North America": "North America", "Americas": "North America",
    "South America": "South America",
    "Oceania (Australia)": "Oceania", "Central Asia (Kyrgyzstan)": "Central Asia",
    "Global": "Global",
}

_S = {s["id"]: s for s in json.load(open("stories.json"))}
_card_ids = [copy[k]["story_id"] for k in _PAGE_ORDER]
_brief_ids = [it["story_id"] for it in copy["briefs"]["items"]]
_all = _card_ids + _brief_ids
assert len(_all) == 35 and len(set(_all)) == 35, f"story count {len(_all)}"
for _sid in _all:
    assert _S[_sid]["status"] == "verified", f"{_sid} not verified"
_rc = Counter(DISPLAY_REGION[_S[i]["region"]] for i in _all)
assert len(_rc) == 9, f"regions {len(_rc)}"
for _ch in copy["region_chips"]["chips"]:
    assert _rc[_ch["region"]] == _ch["count"], f"chip {_ch['region']}: copy {_ch['count']} != recount {_rc[_ch['region']]}"
assert copy["masthead"]["claim_line"] == "35 DATED STORIES · 9 REGIONS · ALL FROM TUE 24 NOV 2026"

# Certainty guard: A7 Sec 6 table (status + displayed outlets; two R-2 shortenings)
EXPECTED = {
    "a4-01": ("CONFIRMED", ["Reuters", "WSJ"]),
    "a6-04": ("OFFICIAL", ["Reuters", "WSJ"]),
    "gap-01": ("OFFICIAL", ["Reuters", "CNN"]),
    "a6-01": ("CONFIRMED", ["AP", "WSJ"]),
    "a6-02": ("CONFIRMED", ["Reuters", "Motley Fool"]),
    "a5-03": ("OFFICIAL", ["AP", "AFP"]),
    "a5-01": ("OFFICIAL", ["Reuters", "Xinhua"]),
    "a4-03": ("OFFICIAL", ["AP", "Argus Media"]),
    "a4-05": ("CONFIRMED", ["Reuters", "Times of Israel"]),
    "a6-07": ("OFFICIAL", ["Reuters", "Gavi"]),
    "gap-04": ("CONFIRMED", ["Reuters", "AP"]),
    "gap-02": ("OFFICIAL", ["WSJ", "Sanofi"]),
    "a6-06": ("OFFICIAL", ["Reuters", "AP"]),
    "a3-02": ("OFFICIAL", ["Fox News"]),
    "a3-05": ("OFFICIAL", ["Reuters", "The Times"]),
    "a3-06": ("OFFICIAL", ["Le Monde"]),
    "a4-04": ("CLAIM", ["Middle East Eye"]),
    "a4-10": ("CONFIRMED", ["Reuters", "Aviation Today"]),
    "a4-13": ("OFFICIAL", ["IMF"]),
    "a5-04": ("CONFIRMED", ["Reuters", "AP"]),
    "a5-10": ("CONFIRMED", ["Yonhap", "JoongAng Daily"]),
    "a5-06": ("CONFIRMED", ["Reuters", "AP"]),
    "a5-07": ("CONFIRMED", ["Reuters", "USGS"]),
    "a5-11": ("CLAIM", ["Xinhua"]),
    "a3-04": ("CONFIRMED", ["Reuters", "iHeart"]),
    "a6-09": ("OFFICIAL", ["UEFA", "Reuters"]),
    "a4-02": ("CONFIRMED", ["Reuters", "AFP"]),
    "a5-05": ("CONFIRMED", ["AP", "Xinhua"]),
    "a6-03": ("CONFIRMED", ["Reuters", "MarketWatch"]),
    "a3-09": ("CONFIRMED", ["Reuters", "WSJ"]),
    "a4-12": ("OFFICIAL", ["UN News", "Arab News"]),
    "a5-09": ("OFFICIAL", ["Reuters"]),
    "a5-15": ("OFFICIAL", ["Dept of Industry", "pm.gov.au"]),
    "a4-14": ("OFFICIAL", ["Reuters"]),
    "a3-07": ("CONFIRMED", ["Reuters", "USA Today"]),
}
_items = {copy[k]["story_id"]: copy[k] for k in _PAGE_ORDER}
_items.update({it["story_id"]: it for it in copy["briefs"]["items"]})
for _sid, (_st, _srcs) in EXPECTED.items():
    _it = _items[_sid]
    assert _it["status_word"] == _st, f"{_sid}: status {_it['status_word']} != A7 {_st}"
    assert _it["sources"] == _srcs, f"{_sid}: sources {_it['sources']} != A7 {_srcs}"
    if _st == "CONFIRMED":
        assert len(_srcs) >= 2, f"{_sid}: CONFIRMED with <2 displayed outlets"
_counts = Counter(v[0] for v in EXPECTED.values())
assert _counts == Counter({"CONFIRMED": 16, "OFFICIAL": 17, "CLAIM": 2}), _counts
assert copy["lead_sec_1"]["dek"] == "Cleared: racketeering, obstruction; sentencing 14 Sep 2027", "R-1 dek drift"

# Badge guard (C4): badge never repeats a headline number verbatim
for _k in _PAGE_ORDER:
    _c = copy[_k]
    if "badge" in _c:
        for _num in re.findall(r"\d[\d,.]*%?", _c["headline"]):
            assert _num not in _c["badge"], f"{_k}: badge repeats headline number {_num}"

# Strip non-duplication guard (D2): numerals must not appear elsewhere
_rest = json.dumps({k: v for k, v in copy.items() if k not in ("numbers_strip", "meta")}, ensure_ascii=False)
for _fg in copy["numbers_strip"]["figures"]:
    assert _fg["numeral"] not in _rest, f"strip numeral {_fg['numeral']} duplicated elsewhere"
assert "since August" in copy["numbers_strip"]["figures"][0]["caption"]
assert "end-2025" not in copy["numbers_strip"]["figures"][3]["caption"]
assert "$40m" not in copy["feature_10"]["dek"]

# Date-integrity + banned-source guard (outside DATE CHECK + meta)
_blob = json.dumps({k: v for k, v in copy.items() if k not in ("datecheck", "meta")}, ensure_ascii=False)
FORBIDDEN = ["19 November", "21 Nov", "17 Nov", "October", "5,678", "11,613",
             "Sparta", "meningitis", "15:42", "18:06", "272",
             "Press TV", "ABNA24", "SOFX", "BigGo", "BM Magazine", "FXStreet",
             "Investopedia", "NY Post", "Mizzima", "Kayhan", "europesays",
             "AnewZ", "Norvan", "Finnhub", "Deep Draft",
             "Asda", "Bitcoin", "Senegal", "king tide", "HRW", "800+",
             "GTA", "Binance", "El Chapo", "18 FIELDS", "38 DATED",
             "25 MORE STORIES", "C = 2+ outlets", "Pins 1-13",
             "1ST FOREIGN CREW", "BROOKLYN · TECH", "WORLD · MARKETS",
             "end-2025", "5,700", "three seas", "9 KILLED", "21:00 Anthropic",
             "wounded in Riyadh", "Huawei counts guilty", "Dow Jones close"]
for _s in FORBIDDEN:
    assert _s not in _blob, f"forbidden string present: {_s!r}"
assert "header_legend" not in copy["briefs"]
assert all("code" not in it for it in copy["briefs"]["items"])
assert [it["number"] for it in copy["briefs"]["items"]] == list(range(14, 36))
assert len(copy["datecheck"]["items"]) == 5
assert len(copy["timeline"]["pins"]) == 5

print(f"guards OK: 35 stories / 9 regions {dict(_rc)}; certainty 16/17/0/2; "
      f"footer {len(_footer_sources)} outlets == displayed set; date-integrity clean")

with open("copy.json", "w", encoding="utf-8") as f:
    json.dump(copy, f, indent=2, ensure_ascii=False)
print("copy.json written")
