"""HTTP utilities for NullForge."""

import logging
import urllib.request

from pyinfra.context import host
from pyinfra.facts.server import Command


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

CURL_ARGS_STR = " ".join((*CURL_FLAGS, *(f"{k} {v}" for k, v in CURL_ARGS.items())))
"""String representation of curl arguments."""

GITHUB_KEYS_URL = "https://github.com/{user}.keys"
"""Public endpoint serving user's authorized SSH public keys."""


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
        if str(host.get_fact(Command, f"{probe} >/dev/null 2>&1 && echo reachable || true") or "").strip():
            address = candidate
            break

    setattr(host.data, cache_key, address)
    return address


def pin_host_args(hostname: str, port: int = 443) -> dict[str, str]:
    address = reachable_address(hostname, port)
    return {"--resolve": f"{hostname}:{port}:{address}"} if address else {}


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
