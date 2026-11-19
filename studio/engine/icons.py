"""Built-in line icons (stroke = currentColor). No external files, nothing to download."""

_HEAD = ('<svg viewBox="0 0 64 64" width="{s}" height="{s}" fill="none" stroke="currentColor" '
         'stroke-width="3.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">')

_BODY = {
    # palm with a few wrinkle lines
    "hand": ('<path d="M20 31V17M29 28V10M38 28V12M47 31V19"/>'
             '<path d="M20 31v9a14 14 0 0 0 28 0V31"/>'
             '<path d="M20 38l-8-8"/>'
             '<path d="M27 43q5 3 10 0M27 49q5 3 10 0" stroke-width="2.6"/>'),
    "clock": '<circle cx="32" cy="32" r="22"/><path d="M32 18v14l10 6"/>',
    "drop": '<path d="M32 8C32 8 14 30 14 40a18 18 0 0 0 36 0C50 30 32 8 32 8z"/>',
    "thermometer": '<path d="M27 14a5 5 0 0 1 10 0v22.5a11 11 0 1 1-10 0z"/><path d="M32 24v20"/>',
    "jar": ('<rect x="16" y="22" width="32" height="32" rx="6"/>'
            '<rect x="20" y="12" width="24" height="10" rx="3"/><path d="M24 36h16M24 44h10"/>'),
    "cross": '<path d="M26 10h12v16h16v12H38v16H26V38H10V26h16z"/>',
    "alert": '<path d="M32 8L58 54H6z"/><path d="M32 26v14"/><circle cx="32" cy="47" r="1.6" fill="currentColor"/>',
    "clipboard": ('<rect x="14" y="12" width="36" height="44" rx="5"/><rect x="24" y="7" width="16" height="9" rx="3"/>'
                  '<path d="M22 28h20M22 38h20M22 48h12"/>'),
    "info": '<circle cx="32" cy="32" r="22"/><path d="M32 30v14"/><circle cx="32" cy="21" r="1.8" fill="currentColor"/>',
}

ICON_NAMES = sorted(_BODY)


def svg(name, size=96):
    if name not in _BODY:
        raise KeyError(f"unknown icon '{name}'. Available: {', '.join(ICON_NAMES)}")
    return _HEAD.format(s=int(size)) + _BODY[name] + "</svg>"
