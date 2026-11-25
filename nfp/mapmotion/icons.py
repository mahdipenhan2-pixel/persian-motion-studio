"""NFP Map Motion - M2e: marker shapes (made for this project, simple geometric forms; no outside artwork).

Every shape is drawn about its own centre (0, 0) in a box of size 1 (from -0.5 to 0.5) and scaled to the marker size
in SCREEN pixels; plane and ship point along +x (heading 0 = east) and are rotated to the route's heading_deg.
  pin   a map pin whose tip is the place (the tip is at (0, 0); the head above it)
  dot   a filled circle            ring  a circle outline            plane / ship  a direction marker
"""
from .svg import el, num

SHAPES = {
    "plane": "M0.5 0L0.08 -0.1L-0.05 -0.48L-0.14 -0.48L-0.1 -0.1L-0.38 -0.08L-0.46 -0.22L-0.52 -0.22L-0.48 0L-0.52 0.22L-0.46 0.22"
             "L-0.38 0.08L-0.1 0.1L-0.14 0.48L-0.05 0.48L0.08 0.1Z",
    "ship": "M0.5 0L0.25 -0.2L-0.45 -0.2L-0.5 -0.12L-0.5 0.12L-0.45 0.2L0.25 0.2Z",
    "pin": "M0 0C-0.12 -0.28 -0.32 -0.42 -0.32 -0.66A0.32 0.32 0 1 1 0.32 -0.66C0.32 -0.42 0.12 -0.28 0 0Z",
}


def marker(kind, x, y, size, color, stroke, opacity=1.0, heading=0.0):
    """SVG for one marker at screen (x, y); '' for 'none'."""
    if kind == "none" or opacity <= 0:
        return ""
    op = None if opacity >= 1 else opacity
    if kind == "dot":
        return el("circle", (("cx", x), ("cy", y), ("r", size / 2), ("fill", color), ("stroke", stroke), ("stroke-width", max(1.0, size / 8)), ("opacity", op)))
    if kind == "ring":
        return el("circle", (("cx", x), ("cy", y), ("r", size / 2), ("fill", "none"), ("stroke", color), ("stroke-width", max(1.5, size / 6)), ("opacity", op)))
    rot = f" rotate({num(heading)})" if kind in ("plane", "ship") else ""
    return el("path", (("d", SHAPES[kind]), ("transform", f"translate({num(x)} {num(y)}){rot} scale({num(size)})"), ("fill", color),
                       ("stroke", stroke), ("stroke-width", 0.06), ("opacity", op)))
