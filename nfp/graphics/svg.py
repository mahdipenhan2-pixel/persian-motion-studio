"""NFP Graphics - G3: a small deterministic SVG writer. Standard library.

The same rules as nfp/mapmotion/svg.py (repeated, not imported, so the Graphics core depends on no other engine):
numbers with at most 3 decimals, trailing zeros removed, -0 written 0; attributes in the order given (None is left out);
text and attribute values XML-escaped. The same input gives the same bytes on every run and machine.
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
