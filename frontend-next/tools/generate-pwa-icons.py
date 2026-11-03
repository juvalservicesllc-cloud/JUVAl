"""Deterministic JUVAl J monogram PNGs; stdlib only, no build dependency."""
from pathlib import Path
import struct
import zlib


def icon(size: int) -> bytes:
    glyph = ("11111", "00010", "00010", "00010", "10010", "10010", "01100")
    rows = bytearray()
    for y in range(size):
        rows.append(0)  # PNG filter: None
        for x in range(size):
            gx = int((x / size - 0.25) * 10)
            gy = int((y / size - 0.15) * 10)
            white = 0.25 <= x / size < 0.75 and 0.15 <= y / size < 0.85 and 0 <= gx < 5 and 0 <= gy < 7 and glyph[gy][gx] == "1"
            rows.extend((255, 255, 255) if white else (10, 125, 36))

    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack("!I", len(data)) + kind + data + struct.pack("!I", zlib.crc32(kind + data))

    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack("!2I5B", size, size, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(bytes(rows), 9)) + chunk(b"IEND", b"")


if __name__ == "__main__":
    target = Path(__file__).resolve().parents[1] / "public"
    for size in (192, 512):
        (target / f"icon-{size}.png").write_bytes(icon(size))
