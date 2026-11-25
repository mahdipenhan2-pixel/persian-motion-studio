"""NFP Timeline - read the format, pixel size and EXIF orientation of a local PNG / JPEG from its header (stdlib only).

info(path) -> {"format": "png" | "jpeg", "width": int, "height": int, "orientation": 1..8}; raises ImageError otherwise.
A JPEG whose EXIF orientation is not 1 is drawn rotated by browsers but its stored size is not rotated: such files are
reported so they can be re-saved upright (no silent guessing).
"""
import struct


class ImageError(ValueError):
    pass


def _exif_orientation(seg):
    """Orientation tag (0x0112) of IFD0 in an APP1 'Exif' segment payload; 1 when absent."""
    if not seg.startswith(b"Exif\0\0") or len(seg) < 14:
        return 1
    t = seg[6:]
    bo = {b"II": "<", b"MM": ">"}.get(t[:2])
    if bo is None:
        return 1
    try:
        off = struct.unpack(bo + "I", t[4:8])[0]
        n = struct.unpack(bo + "H", t[off:off + 2])[0]
        for k in range(n):
            e = t[off + 2 + 12 * k: off + 14 + 12 * k]
            tag, typ, cnt = struct.unpack(bo + "HHI", e[:8])
            if tag == 0x0112 and typ == 3:
                return struct.unpack(bo + "H", e[8:10])[0]
    except struct.error:
        return 1
    return 1


def info(path):
    with open(path, "rb") as f:
        head = f.read(32)
        if head[:8] == b"\x89PNG\r\n\x1a\n":
            if head[12:16] != b"IHDR":
                raise ImageError("PNG without an IHDR header")
            w, h = struct.unpack(">II", head[16:24])
            if not w or not h:
                raise ImageError("PNG with zero size")
            return {"format": "png", "width": w, "height": h, "orientation": 1}
        if head[:2] != b"\xff\xd8":
            raise ImageError("not a PNG or JPEG file")
        f.seek(2)
        orient = 1
        while True:
            b = f.read(1)
            while b and b != b"\xff":
                b = f.read(1)
            while b == b"\xff":
                b = f.read(1)
            if not b:
                raise ImageError("JPEG without a frame header")
            m = b[0]
            if m in (0xD8, 0x01) or 0xD0 <= m <= 0xD7:
                continue
            if m == 0xD9:
                raise ImageError("JPEG ends before its frame header")
            ln = struct.unpack(">H", f.read(2))[0]
            seg = f.read(ln - 2)
            if len(seg) < ln - 2:
                raise ImageError("truncated JPEG")
            if m == 0xE1:
                orient = _exif_orientation(seg) if orient == 1 else orient
            if 0xC0 <= m <= 0xCF and m not in (0xC4, 0xC8, 0xCC):
                h, w = struct.unpack(">HH", seg[1:5])
                if not w or not h:
                    raise ImageError("JPEG with zero size")
                return {"format": "jpeg", "width": w, "height": h, "orientation": orient}
