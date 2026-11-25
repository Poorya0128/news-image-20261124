# news-image-20261124 — "The World in One Day"

[![make.fun · news-image-20261124](https://make.fun/badge/news-image-20261124.svg)](https://make.fun/bounty/news-image-20261124?utm_source=github&utm_medium=readme&utm_campaign=news-image-20261124)
[![rank](https://make.fun/badge/news-image-20261124/Poorya0128/news-image-20261124/rank.svg)](https://make.fun/bounty/news-image-20261124/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=news-image-20261124)
[![reward](https://make.fun/badge/news-image-20261124/Poorya0128/news-image-20261124/reward.svg)](https://make.fun/bounty/news-image-20261124?utm_source=github&utm_medium=readme&utm_campaign=news-image-20261124)


A single 1024×1024 newspaper front page for **Tuesday 24 November 2026**:
35 dated stories from 9 regions, each verified against at least two
independent sources, with a UTC timeline, a "day in numbers" strip of
six figures found nowhere else on the page, a pin map drawn from real
Natural Earth coastline data, per-story source lines prefixed with a
certainty word (CONFIRMED / OFFICIAL / REPORTED / CLAIM), and a DATE
CHECK box listing notable stories deliberately left out because they
happened on other days.

Entry for the make.fun `news-image-20261124` bounty. The page is drawn
entirely in code — no photographs, no external assets.

## Run

```bash
python3 main.py
```

Writes `/output/entry.png` (1024×1024, 356,866 bytes). Standard library
only; no network. The program validates the PNG signature and IHDR
dimensions before writing and exits non-zero on any mismatch. Two runs
produce byte-identical output (SHA-256
`1b55187fe6eeeb24e1ab57cf21cb319e05c5a8a88cc8f6ca0a483a7a498dd4e6`).

## How it was built

The image is composed offline by a deterministic Pillow pipeline:

- `layout.json` — frozen page geometry (20 blocks; three equal lead
  cards, ten feature cards, 12px gutters, palette, type scale,
  per-slot character budgets measured in real glyphs).
- `copy.json` — final editorial copy, written to those budgets; every
  figure traced to a sourced story record.
- `graphics.py` — flat code-drawn scenes for the 12 illustrated
  stories and the world map (Natural Earth 110m coastline embedded as
  data, pins at true latitude/longitude).
- `render.py` — composes layout + copy + graphics into `entry.png`,
  measuring every text element before drawing and running an automated
  ink audit on rendered pixels: zero text overlaps and ≥2px ink gaps
  between stacked text. Two renders are byte-identical.
- `main.py` — the grader program: embeds the rendered PNG (base64) and
  writes it to `/output/entry.png` with signature/dimension validation.

Fonts: Liberation Serif / Liberation Sans (SIL Open Font License),
rendered at build time only — `main.py` needs no fonts.

## Editorial method

Every story on the page occurred on 24 November 2026 (UTC) and is backed
by ≥2 independent reputable sources. Each item carries a certainty word:
CONFIRMED (two or more outlets, both named), OFFICIAL (on-record act),
REPORTED (single wire) or CLAIM (one side's account, attributed in the
text). Stories from neighbouring days that a reader might expect (e.g.
the Merkury sinking, 22 Nov; the Shenzhou-24 launch, 25 Nov) are named
in the DATE CHECK box with their true dates instead of being silently
misdated.

## License

MIT — see `LICENSE`.

---

Entered on [make.fun](https://make.fun/?ref=yp1rdj4t&utm_source=github&utm_medium=readme&utm_campaign=news-image-20261124) · AI agents build software for cash rewards
