"""NFP Map Motion - M2e: a small deterministic SVG writer. Standard library.

Numbers are written with at most 3 decimals, trailing zeros removed and -0 written 0, so the same input gives the same
bytes on every run and machine. Attribute order is the order given; text and attribute values are XML-escaped.
"""
from xml.sax.saxutils import escape, quoteattr


def num(v):
    s = f"{float(v):.3f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def attrs(a):
    out = []
    for k, v in a:
        if v is None:
            continue
        if isinstance(v, float) or (isinstance(v, int) and not isinstance(v, bool)):
            v = num(v)
        out.append(f" {k}={quoteattr(str(v))}")
    return "".join(out)


def el(tag, a=(), body=None):
    if body is None:
        return f"<{tag}{attrs(a)}/>"
    return f"<{tag}{attrs(a)}>{body}</{tag}>"


def text(s):
    return escape(str(s))


def path_d(paths, closed):
    """SVG path data from [[(x, y), ...], ...]."""
    out = []
    for p in paths:
        if not p:
            continue
        out.append("M" + " ".join(f"{num(x)} {num(y)}" for x, y in p[:1]) + "".join(f"L{num(x)} {num(y)}" for x, y in p[1:]))
        if closed:
            out.append("Z")
    return "".join(out)
