"""URL slug generation.

Slugs give the mobile and desktop clients a stable, human-readable handle for
a category or product that does not leak a database id.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable

_NON_ALPHANUMERIC = re.compile(r"[^a-z0-9]+")
_EDGE_HYPHENS = re.compile(r"^-+|-+$")


def slugify(value: str, *, max_length: int = 120) -> str:
    """Convert free text into a lowercase, hyphen-separated slug.

    Accented characters are folded to ASCII so that "Flower Pots — Deluxe"
    becomes "flower-pots-deluxe".
    """
    normalised = unicodedata.normalize("NFKD", value)
    ascii_only = normalised.encode("ascii", "ignore").decode("ascii")
    slug = _NON_ALPHANUMERIC.sub("-", ascii_only.lower())
    slug = _EDGE_HYPHENS.sub("", slug)[:max_length]
    return _EDGE_HYPHENS.sub("", slug)


def unique_slug(value: str, exists: Callable[[str], bool], *, max_length: int = 120) -> str:
    """Return a slug that `exists` reports as free, appending -2, -3, ... if needed.

    `exists` is supplied by the service layer so this helper stays free of any
    database dependency.
    """
    base = slugify(value, max_length=max_length) or "item"
    if not exists(base):
        return base

    suffix = 2
    while True:
        candidate = f"{base[: max_length - len(str(suffix)) - 1]}-{suffix}"
        if not exists(candidate):
            return candidate
        suffix += 1
