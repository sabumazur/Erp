import hashlib

from django import template

register = template.Library()

# Muted pastels — all legible with #1e2130 dark text.
_PALETTE = [
    "#dbeafe",  # blue-100
    "#dcfce7",  # green-100
    "#fef9c3",  # yellow-100
    "#ffe4e6",  # rose-100
    "#e0e7ff",  # indigo-100
    "#f3e8ff",  # purple-100
    "#ffedd5",  # orange-100
    "#cffafe",  # cyan-100
    "#fce7f3",  # pink-100
    "#fef3c7",  # amber-100
    "#d1fae5",  # emerald-100
    "#e0f2fe",  # sky-100
]


@register.filter
def avatar_bg(name: str) -> str:
    """Return a stable pastel background color derived from the name."""
    digest = int(hashlib.md5(str(name).encode(), usedforsecurity=False).hexdigest(), 16)
    return _PALETTE[digest % len(_PALETTE)]
