r"""What it is:   A one-off drawing script for the e-mail logo.
What it does: Draws the rootsquares logo mark as PNG files for e-mail (mail apps cannot show SVG) into app/platform/email_assets.
How to run:   From backend/: .venv\Scripts\python.exe scripts\make_email_logo.py
Read before:  frontend/ui/src/components/Wordmark.vue (the mark it copies).
Read after:   docs/setup/25-platform-email.md; email-templates/build_platform.py to preview.

Draws the rootsquares logo mark (frontend/ui/src/components/Wordmark.vue: ink square outline rx 3, stroke 2.2, brass stem forking like roots)
as PNG files for e-mail, because mail apps cannot show SVG. Pure Python (no Pillow). Run: python scripts/make_email_logo.py"""

from __future__ import annotations

import math
import struct
import zlib
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "app" / "platform" / "email_assets"
SIZE, SS = 96, 4  # pixels, subsamples per axis
HALF = 1.1  # stroke 2.2 in a 24-unit box
SEGMENTS = [((12, 4), (12, 13)), ((12, 9), (8, 12)), ((12, 9), (16, 12))]
VARIANTS = {"logo-ink.png": ((0x1C, 0x1A, 0x16), (0x9A, 0x7A, 0x2E)), "logo-cream.png": ((0xF3, 0xEF, 0xE4), (0xD4, 0xA8, 0x5C))}


def _seg(px: float, py: float, a: tuple[float, float], b: tuple[float, float]) -> float:
    dx, dy = b[0] - a[0], b[1] - a[1]
    t = max(0.0, min(1.0, ((px - a[0]) * dx + (py - a[1]) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - (a[0] + t * dx), py - (a[1] + t * dy))


def _box(px: float, py: float) -> float:
    """Distance to the outline of the rounded square (centre 12,12, half side 9, radius 3)."""
    qx, qy = abs(px - 12) - (9 - 3), abs(py - 12) - (9 - 3)
    outside = math.hypot(max(qx, 0), max(qy, 0))
    return abs(outside + min(max(qx, qy), 0) - 3)


def _pixel(ix: int, iy: int, ink: tuple[int, int, int], brass: tuple[int, int, int]) -> tuple[int, int, int, int]:
    r = g = b = a = 0.0
    for sy in range(SS):
        for sx in range(SS):
            px, py = (ix + (sx + 0.5) / SS) * 24 / SIZE, (iy + (sy + 0.5) / SS) * 24 / SIZE
            if min(_seg(px, py, *s) for s in SEGMENTS) <= HALF:
                col = brass
            elif _box(px, py) <= HALF:
                col = ink
            else:
                continue
            r, g, b, a = r + col[0], g + col[1], b + col[2], a + 1
    if a == 0:
        return 0, 0, 0, 0
    return round(r / a), round(g / a), round(b / a), round(255 * a / (SS * SS))


def _png(rows: list[bytes]) -> bytes:
    def chunk(kind: bytes, data: bytes) -> bytes:
        body = kind + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))

    raw = b"".join(b"\x00" + row for row in rows)
    header = chunk(b"IHDR", struct.pack(">IIBBBBB", SIZE, SIZE, 8, 6, 0, 0, 0))
    return b"\x89PNG\r\n\x1a\n" + header + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b"")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, (ink, brass) in VARIANTS.items():
        rows = [b"".join(bytes(_pixel(x, y, ink, brass)) for x in range(SIZE)) for y in range(SIZE)]
        (OUT / name).write_bytes(_png(rows))
        print("wrote", OUT / name)


if __name__ == "__main__":
    main()
