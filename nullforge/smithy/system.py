"""System utilities for NullForge."""

import re

from pyinfra.context import host
from pyinfra.facts.files import FileContents
from pyinfra.facts.hardware import Memory


_LOCALE_GEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z0-9-]+)?(?:@[A-Za-z0-9-]+)?\s+[A-Z][A-Z0-9-]*")
"""A `locale.gen` entry: `name[.charset][@modifier] CHARMAP`, e.g. `en_US.UTF-8 UTF-8`.

The commented-out entries this file is mostly made of are indistinguishable from its prose
header by shape alone, so both tokens are matched rather than just counted.
"""


def get_total_memory(default: int = 1024) -> int:
    """Return host's total RAM in MB."""

    cache_key = "_nullforge_total_memory_mb"
    if hasattr(host.data, cache_key):
        return getattr(host.data, cache_key)

    memory = host.get_fact(Memory)
    total_mb = int(memory) if memory else default

    setattr(host.data, cache_key, total_mb)
    return total_mb


def get_supported_locales() -> list[str]:
    """Get list of supported locales from /etc/locale.gen."""

    cache_key = "_nullforge_supported_locales"
    if hasattr(host.data, cache_key):
        return getattr(host.data, cache_key)

    locales = []
    for line in host.get_fact(FileContents, path="/etc/locale.gen") or []:
        line = line.strip()
        if not line:
            continue
        if line.startswith("#"):
            line = line[1:].strip()

        if _LOCALE_GEN_RE.fullmatch(line):
            name, charmap = line.split()
            locales.append(f"{name} {charmap}")

    setattr(host.data, cache_key, locales)
    return locales


def detect_best_locale(preferred: str | None = None) -> str | None:
    """Return the best available locale gen line, or ``None`` if none are supported.

    A ``preferred`` locale is honored when available (by exact or name-prefix match);
    otherwise a sensible UTF-8 default is chosen. ``None`` is returned only when the
    host reports no supported locales at all, so callers never need a separate
    fallback call.
    """

    supported = get_supported_locales()
    if not supported:
        return None

    preferred = (preferred or "").strip()
    if preferred:
        if preferred in supported:
            return preferred
        pref_name = preferred.split()[0]
        for supp in supported:
            if supp.startswith(pref_name):
                return supp

    defaults = ["en_US.UTF-8 UTF-8", "C.UTF-8 UTF-8", "en_GB.UTF-8 UTF-8"]
    for def_loc in defaults:
        if def_loc in supported:
            return def_loc

    for loc in supported:
        if "UTF-8" in loc.upper():
            return loc

    return supported[0]
