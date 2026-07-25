"""Architecture utilities for NullForge."""

import platform

from pyinfra.context import host
from pyinfra.facts.server import Arch


def _normalize(a: str | None) -> str:
    return {
        "x86_64": "x86_64",
        "amd64": "x86_64",
        "aarch64": "arm64",
        "arm64": "arm64",
    }.get(a or "", a or "x86_64")


def arch_id() -> str:
    """Normalize arch id where vendors differ."""

    cache_key = "_nullforge_arch_id"
    try:
        if hasattr(host.data, cache_key):
            return getattr(host.data, cache_key)
        result = _normalize(host.get_fact(Arch))
        setattr(host.data, cache_key, result)
        return result
    except AttributeError:
        return _normalize(platform.machine())


def deb_arch() -> str:
    return {
        "x86_64": "amd64",
        "arm64": "arm64",
    }.get(arch_id(), "amd64")
