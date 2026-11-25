#!/usr/bin/env python3
"""Entrypoint for make.fun bounty news-image-20261124.

The newspaper image was rendered ahead of time by the newsroom pipeline
(render.py / graphics.py in this repo). This script checks the rendered
PNG is intact and places it in MAKEFUN_OUTPUT_DIR (default /output),
where the grader expects it. Standard library only; no network access.
"""

import os
import struct
import sys
import zlib

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
LIMIT = 1024 * 1024
WANT_W = 1024
WANT_H = 1024


def check_png(blob):
    """Raise ValueError unless blob is a whole 1024x1024 PNG <= 1 MiB."""
    if len(blob) > LIMIT:
        raise ValueError("image is %d bytes, over the 1 MiB cap" % len(blob))
    if blob[:8] != PNG_MAGIC:
        raise ValueError("missing PNG signature")
    offset = 8
    dims = None
    while offset + 8 <= len(blob):
        size = struct.unpack(">I", blob[offset:offset + 4])[0]
        kind = blob[offset + 4:offset + 8]
        stop = offset + 12 + size
        if stop > len(blob):
            raise ValueError("chunk %r runs past end of file" % kind)
        want_crc = struct.unpack(">I", blob[stop - 4:stop])[0]
        got_crc = zlib.crc32(blob[offset + 4:stop - 4]) & 0xFFFFFFFF
        if want_crc != got_crc:
            raise ValueError("CRC mismatch in chunk %r" % kind)
        if kind == b"IHDR":
            dims = struct.unpack(">II", blob[offset + 8:offset + 16])
        offset = stop
    if dims is None:
        raise ValueError("no IHDR chunk found")
    if dims != (WANT_W, WANT_H):
        raise ValueError("image is %dx%d, expected %dx%d"
                         % (dims[0], dims[1], WANT_W, WANT_H))
    if offset != len(blob):
        raise ValueError("extra bytes after final chunk")


def run():
    here = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(here, "entry.png"), "rb") as fh:
        blob = fh.read()
    check_png(blob)
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR") or "/output"
    os.makedirs(out_dir, exist_ok=True)
    target = os.path.join(out_dir, "entry.png")
    with open(target, "wb") as fh:
        fh.write(blob)
    print("entry.png -> %s (%d bytes)" % (target, len(blob)))
    return 0


if __name__ == "__main__":
    sys.exit(run())
