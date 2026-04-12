"""Network utilities for NullForge."""

import re

from pyinfra.context import host
from pyinfra.facts.files import FileContents
from pyinfra.facts.server import Command, KernelModules


def conntrack_max_for(ram_mb: int) -> int:
    """Cap conntrack to ~2% of RAM as a backpressure ceiling (~300 B/entry)."""

    entries = int(ram_mb * 1024 * 1024 * 0.02 / 300)
    return max(16384, min(entries, 512 * 1024))


def module_loaded(module: str) -> bool:
    """Return True if named kernel module is currently loaded."""

    return module in _loaded_kernel_modules()


def _loaded_kernel_modules() -> dict[str, dict]:
    cache_key = "_nullforge_kernel_modules"
    if hasattr(host.data, cache_key):
        return getattr(host.data, cache_key)

    modules: dict[str, dict] = host.get_fact(KernelModules) or {}

    setattr(host.data, cache_key, modules)
    return modules


_TUNNEL_IFACE_RE = re.compile(
    r"^(?:warp|tun\d*|tap\d*|wg\d*|zt[0-9a-f]*|tailscale|ts\d|"
    r"docker\d*|br-[0-9a-f]+|veth[0-9a-f]+|cni\d*|cali[0-9a-f]+|"
    r"flannel|weave|ipip|sit|gre|ip6tnl|ip6gre)"
)


def _ipv6_grub_disabled() -> bool:
    """Return True if GRUB is configured with ipv6.disable=1."""

    cache_key = "_nullforge_ipv6_grub_disabled"
    if hasattr(host.data, cache_key):
        return getattr(host.data, cache_key)

    grub_contents = host.get_fact(FileContents, path="/etc/default/grub") or []
    disabled = any("ipv6.disable=1" in line for line in grub_contents)

    setattr(host.data, cache_key, disabled)
    return disabled


def _ipv6_global_addrs_raw() -> str:
    cache_key = "_nullforge_ipv6_global_raw"
    if hasattr(host.data, cache_key):
        return getattr(host.data, cache_key)

    raw = host.get_fact(Command, "ip -6 -o addr show scope global 2>/dev/null || true") or ""
    setattr(host.data, cache_key, raw)
    return raw


def has_ipv6(*, exclude_iface: str | None = None) -> bool:
    """Return whether the host has usable global IPv6."""

    if exclude_iface is None:
        cache_key = "_nullforge_ipv6_enabled"
        if hasattr(host.data, cache_key):
            return getattr(host.data, cache_key)

    if _ipv6_grub_disabled():
        setattr(host.data, "_nullforge_ipv6_enabled", False)
        return False

    raw = _ipv6_global_addrs_raw()

    result = False
    for line in raw.splitlines():
        parts = line.split(maxsplit=3)
        if len(parts) < 3:
            continue
        iface = parts[1].rstrip(":")
        if exclude_iface and iface == exclude_iface:
            continue
        if _TUNNEL_IFACE_RE.match(iface):
            continue
        if parts[2] == "inet6":
            result = True
            break

    if exclude_iface is None:
        setattr(host.data, "_nullforge_ipv6_enabled", result)
    return result
