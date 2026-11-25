#!/usr/bin/env python3
"""A12: regenerate main.py (grader program) embedding entry.png.

Same template as the 1cec3843 build: stdlib only, validates PNG
signature + IHDR dimensions + size limit, writes /output/entry.png,
re-reads and verifies. Deterministic.
"""
import base64
import hashlib
import os

HERE = os.path.dirname(os.path.abspath(__file__))
data = open(os.path.join(HERE, "entry.png"), "rb").read()
assert data[:8] == b"\x89PNG\r\n\x1a\n" and len(data) <= 1048576
b64 = base64.b64encode(data).decode("ascii")
chunks = [b64[i:i + 100] for i in range(0, len(b64), 100)]
body = "\n".join(f'    "{c}"' for c in chunks)

src = f'''#!/usr/bin/env python3
"""news-image-20261124 — grader program (Python 3 stdlib only, no network).

Writes the deterministic 1024x1024 front-page PNG for Tuesday 24 November
2026 to /output/entry.png. The image bytes are embedded below (base64);
they were rendered offline by render.py from layout.json + copy.json +
graphics.py. This program validates the PNG signature and IHDR dimensions
before writing and fails loudly on any mismatch.
"""
import base64
import os
import struct
import sys

_PNG_B64 = (
{body}
)

EXPECTED_WIDTH = 1024
EXPECTED_HEIGHT = 1024
MAX_BYTES = 1048576
OUT_PATH = "/output/entry.png"


def fail(msg):
    print("ERROR: " + msg, file=sys.stderr)
    sys.exit(1)


def main():
    data = base64.b64decode(_PNG_B64)
    # validate PNG signature
    if data[:8] != b"\\x89PNG\\r\\n\\x1a\\n":
        fail("embedded data is not a PNG (bad signature)")
    # validate IHDR chunk + dimensions
    if len(data) < 24 or data[12:16] != b"IHDR":
        fail("PNG missing IHDR chunk")
    width, height = struct.unpack(">II", data[16:24])
    if (width, height) != (EXPECTED_WIDTH, EXPECTED_HEIGHT):
        fail("PNG is %dx%d, expected %dx%d" % (width, height, EXPECTED_WIDTH, EXPECTED_HEIGHT))
    if len(data) > MAX_BYTES:
        fail("PNG is %d bytes, over the %d-byte limit" % (len(data), MAX_BYTES))
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "wb") as fh:
        fh.write(data)
    # re-read and verify what landed on disk
    with open(OUT_PATH, "rb") as fh:
        written = fh.read()
    if written != data:
        fail("written file does not match embedded bytes")
    print("wrote %s (%d bytes, %dx%d)" % (OUT_PATH, len(written), width, height))


if __name__ == "__main__":
    main()
'''

with open(os.path.join(HERE, "main.py"), "w", encoding="utf-8") as f:
    f.write(src)
print(f"main.py regenerated: entry.png {len(data)} bytes sha256 {hashlib.sha256(data).hexdigest()}")
