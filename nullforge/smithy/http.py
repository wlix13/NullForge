"""HTTP utilities for NullForge."""

import logging
import shlex
import urllib.request
from dataclasses import dataclass

from pyinfra.context import host
from pyinfra.facts.server import Command

from nullforge.molds import FeaturesMold


LOG = logging.getLogger("pyinfra")


CURL_FLAGS = (
    "--compressed",
    "--fail",
    "--retry-connrefused",
    "--tlsv1.2",
)
"""Curl options that take no value."""

CURL_ARGS = {
    "--retry": "3",
    "--connect-timeout": "10",
    "--max-time": "120",
    "--proto": "=https",
}
"""Robust curl options for reliable downloads."""

WARP_TRACE_URL = "https://www.cloudflare.com/cdn-cgi/trace"
"""Reports `warp=on` when the request egressed through WARP."""

GITHUB_KEYS_URL = "https://github.com/{user}.keys"
"""Public endpoint serving user's authorized SSH public keys."""


@dataclass(frozen=True)
class Egress:
    """Path a download takes off this host."""

    interface: str | None = None
    resolve: str | None = None

    def curl_args(self) -> dict[str, str]:
        args: dict[str, str] = {}
        if self.interface:
            args["--interface"] = self.interface
        if self.resolve:
            args["--resolve"] = self.resolve
        return args


def _command_output(command: str) -> str:
    return str(host.get_fact(Command, command) or "").strip()


def _reaches(url: str, egress: Egress) -> bool:
    opts = " ".join(f"{key} {shlex.quote(value)}" for key, value in egress.curl_args().items())
    probe = (
        f"curl -sS -o /dev/null -L -r 0-0 --connect-timeout 5 --max-time 15 --proto =https {opts} {shlex.quote(url)}"
    )
    return bool(_command_output(f"{probe} >/dev/null 2>&1 && echo reachable || true"))


def warp_interface() -> str | None:
    """WARP interface confirmed to carry egress, if `features.warp` is active."""

    cache_key = "_nullforge_warp_interface"
    if hasattr(host.data, cache_key):
        return getattr(host.data, cache_key)

    iface = None
    features = getattr(host.data, "features", None)
    if isinstance(features, FeaturesMold) and features.warp.is_active:
        candidate = features.warp.iface
        trace = (
            f"curl -sS --interface {shlex.quote(candidate)} --connect-timeout 5 --max-time 10 {WARP_TRACE_URL}"
            " 2>/dev/null | grep -E '^warp=(on|plus)$' || true"
        )
        if _command_output(trace):
            iface = candidate

    setattr(host.data, cache_key, iface)
    return iface


def egress_for(url: str, *, resolve: str | None = None) -> Egress:
    """Default route when it reaches `url`, else WARP when the host has it."""

    cache_key = f"_nullforge_egress_{url}"
    if hasattr(host.data, cache_key):
        return getattr(host.data, cache_key)

    egress = Egress(resolve=resolve)
    if not _reaches(url, egress):
        iface = warp_interface()
        if iface and _reaches(url, Egress(interface=iface)):
            egress = Egress(interface=iface)
            LOG.info(f"[{host.name}] {url} is unreachable directly, downloading via WARP interface '{iface}'")
        else:
            LOG.warning(f"[{host.name}] {url} is unreachable {'directly and via WARP' if iface else 'directly'}")

    setattr(host.data, cache_key, egress)
    return egress


def curl_args(url: str, *, resolve: str | None = None) -> dict[str, str]:
    """`CURL_ARGS` plus egress options for `url`."""

    return {**CURL_ARGS, **egress_for(url, resolve=resolve).curl_args()}


def curl_args_str(url: str) -> str:
    """`curl_args()` and `CURL_FLAGS` rendered for a shell command."""

    return " ".join((*CURL_FLAGS, *(f"{key} {shlex.quote(value)}" for key, value in curl_args(url).items())))


def reachable_address(hostname: str, port: int = 443) -> str | None:
    """First address of `hostname` this host can actually talk HTTPS to, if any."""

    cache_key = f"_nullforge_reachable_{hostname}"
    if hasattr(host.data, cache_key):
        return getattr(host.data, cache_key)

    address = None
    listed = host.get_fact(Command, f"getent ahostsv4 {hostname} | awk '{{print $1}}' | sort -u || true")
    for candidate in str(listed or "").split():
        # HTTPS answer proves path works; status code is irrelevant
        probe = f"curl -sS -o /dev/null --connect-timeout 5 --resolve {hostname}:{port}:{candidate} https://{hostname}/"
        if _command_output(f"{probe} >/dev/null 2>&1 && echo reachable || true"):
            address = candidate
            break

    setattr(host.data, cache_key, address)
    return address


def fetch_text(url: str, *, timeout: int = 10, headers: dict[str, str] | None = None) -> str:
    """Fetch text from HTTPS URL on control node."""

    if not url.startswith("https://"):
        raise ValueError(f"Refusing non-HTTPS URL: {url}")

    headers = headers or {}
    request = urllib.request.Request(url, headers=headers)  # noqa: S310 - https-only guard above
    with urllib.request.urlopen(request, timeout=timeout) as resp:  # noqa: S310 - https-only guard above
        return resp.read().decode("utf-8")


def fetch_github_keys(username: str | None) -> list[str]:
    """Fetch public SSH keys for GitHub user."""

    if not username:
        return []

    try:
        contents = fetch_text(GITHUB_KEYS_URL.format(user=username))
    except Exception as e:
        LOG.warning(f"Failed to fetch GitHub SSH keys for '{username}': {e}")
        return []

    return contents.splitlines()
