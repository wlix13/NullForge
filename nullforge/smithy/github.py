"""GitHub release metadata helpers for NullForge.

These run on the *control node* at plan time (like `fetch_github_keys`), not on the
target. They resolve checksums and detect the right asset for a release so that the
target-side installers in `smithy/install.py` can verify downloads and, optionally,
pick assets without a hand-written URL per tool.

Everything degrades gracefully: if the API is unreachable or rate-limited, resolvers
return ``None`` and callers fall back to their existing (unverified) behaviour. Set
``GITHUB_TOKEN`` (or ``GH_TOKEN``) in the control-node environment to raise the API
rate limit from 60 to 5000 requests/hour.
"""

import json
import logging
import os
import re
from contextlib import suppress

from nullforge.smithy.arch import arch_id
from nullforge.smithy.http import fetch_text


LOG = logging.getLogger("pyinfra")

GITHUB_API = "https://api.github.com"
"""REST API base; queried from the control node only."""

_DOWNLOAD_URL_RE = re.compile(
    r"^https://github\.com/(?P<repo>[^/]+/[^/]+)/releases/"
    r"(?:download/(?P<tag>[^/]+)|(?P<latest>latest)/download)/(?P<asset>[^/]+)$"
)
"""Matches the release-asset URLs produced by `Versions._release_url`."""

_CHECKSUM_HINTS = ("checksum", "sha256", "sha256sums", "sha256sum")
"""Substrings that flag an assets-wide checksums manifest."""

_SHA256_RE = re.compile(r"\b[0-9a-f]{64}\b")

_RELEASE_CACHE: dict[tuple[str, str], dict | None] = {}
"""Per-run cache so a single deploy hits the API at most once per (repo, tag)."""

# Arch/OS token synonyms, mirroring how release assets are commonly named.
_ARCH_TOKENS: dict[str, tuple[str, ...]] = {
    "x86_64": ("x86_64", "amd64", "x64", "64bit"),
    "arm64": ("arm64", "aarch64"),
}
_ALL_ARCH_TOKENS = {token for tokens in _ARCH_TOKENS.values() for token in tokens}
_OS_TOKENS: dict[str, tuple[str, ...]] = {
    "linux": ("linux",),
    "darwin": ("darwin", "macos", "apple"),
    "windows": ("windows", "win"),
}
_ALL_OS_TOKENS = {token for tokens in _OS_TOKENS.values() for token in tokens}

# Assets that are never the binary we want.
_NON_BINARY_SUFFIXES = (".sha256", ".sha256sum", ".sig", ".asc", ".pem", ".pub", ".txt", ".sbom", ".json")


def _token() -> str | None:
    return os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")


def _headers() -> dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = _token()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def fetch_release(repo: str, tag: str) -> dict | None:
    """Fetch release metadata for ``owner/repo`` at ``tag`` (``"latest"`` supported).

    Returns the parsed JSON object, or ``None`` on any failure (unreachable API,
    rate limit, unknown tag). Results are cached for the duration of the run.
    """

    cache_key = (repo, tag)
    if cache_key in _RELEASE_CACHE:
        return _RELEASE_CACHE[cache_key]

    path = "releases/latest" if tag == "latest" else f"releases/tags/{tag}"
    url = f"{GITHUB_API}/repos/{repo}/{path}"
    release: dict | None = None
    try:
        release = json.loads(fetch_text(url, headers=_headers()))
    except Exception as exc:  # noqa: BLE001 - network/JSON errors all degrade to None
        LOG.warning(f"GitHub release lookup failed for {repo}@{tag}: {exc}")

    _RELEASE_CACHE[cache_key] = release
    return release


def _find_asset(release: dict, asset_name: str) -> dict | None:
    for asset in release.get("assets", []):
        if asset.get("name") == asset_name:
            return asset
    return None


def _digest_sha256(asset: dict) -> str | None:
    """Read the API-provided ``digest`` field (``"sha256:<hex>"``) if present."""

    digest = asset.get("digest") or ""
    prefix = "sha256:"
    if digest.startswith(prefix):
        candidate = digest[len(prefix) :].strip().lower()
        if _SHA256_RE.fullmatch(candidate):
            return candidate
    return None


def _sha256_from_manifest(release: dict, asset_name: str) -> str | None:
    """Locate a checksums asset in the release and parse the line for ``asset_name``."""

    for asset in release.get("assets", []):
        name = (asset.get("name") or "").lower()
        is_per_asset = name == f"{asset_name.lower()}.sha256"
        is_manifest = any(hint in name for hint in _CHECKSUM_HINTS)
        if not (is_per_asset or is_manifest):
            continue

        url = asset.get("browser_download_url")
        if not url:
            continue
        with suppress(Exception):
            body = fetch_text(url)
            found = _parse_checksums(body, asset_name)
            if found:
                return found
    return None


def _parse_checksums(body: str, asset_name: str) -> str | None:
    """Extract the sha256 for ``asset_name`` from a checksums file body.

    Supports both multi-asset manifests (``<hex>  <name>`` / ``<hex> *<name>``) and
    single-asset files that contain only the hash (optionally with a filename).
    """

    target = asset_name.rsplit("/", 1)[-1]
    lone: str | None = None
    for raw in body.splitlines():
        line = raw.strip()
        if not line:
            continue
        match = _SHA256_RE.search(line)
        if not match:
            continue
        digest = match.group(0).lower()
        rest = (line[: match.start()] + line[match.end() :]).strip().lstrip("*").strip()
        if not rest:
            lone = digest  # bare "<hex>" — remember as a single-asset fallback
            continue
        if rest.rsplit("/", 1)[-1].lstrip("*") == target:
            return digest
    return lone


def asset_sha256(release: dict, asset_name: str) -> str | None:
    """Best-effort sha256 for ``asset_name``: API digest first, then a checksums file."""

    asset = _find_asset(release, asset_name)
    if asset is not None:
        digest = _digest_sha256(asset)
        if digest:
            return digest
    return _sha256_from_manifest(release, asset_name)


def parse_download_url(url: str) -> tuple[str, str, str] | None:
    """Split a GitHub release-asset URL into ``(repo, tag, asset_name)``.

    Returns ``None`` for anything that is not a matching GitHub release URL (including
    non-string input), so callers degrade to "no checksum" rather than raising.
    """

    if not isinstance(url, str):
        return None
    match = _DOWNLOAD_URL_RE.match(url)
    if not match:
        return None
    tag = "latest" if match.group("latest") else match.group("tag")
    return match.group("repo"), tag, match.group("asset")


def sha256_for_download_url(url: str) -> str | None:
    """Resolve the sha256 for a release-asset download URL, or ``None`` if unavailable.

    This is the ergonomic entry point: any URL from `Versions` (e.g. ``telemt_tar()``)
    can be verified without knowing its repo/tag/asset separately.
    """

    parsed = parse_download_url(url)
    if parsed is None:
        return None
    repo, tag, asset_name = parsed
    release = fetch_release(repo, tag)
    if release is None:
        return None
    return asset_sha256(release, asset_name)


def select_asset(
    release: dict,
    *,
    arch: str | None = None,
    os_name: str = "linux",
    include: tuple[str, ...] = (),
    exclude: tuple[str, ...] = (),
) -> dict | None:
    """Pick the release asset best matching the current arch/OS (bin-style matcher).

    Scores each asset by OS/arch token match and ``include`` hints, rejecting assets
    that clearly target a different OS or arch. Returns the highest-scoring asset dict,
    or ``None`` when nothing matches. Useful for tools whose asset names are awkward to
    template, or for resolving a concrete asset from a ``latest`` release.
    """

    want_arch = arch or arch_id()
    arch_tokens = _ARCH_TOKENS.get(want_arch, (want_arch,))
    os_tokens = _OS_TOKENS.get(os_name, (os_name,))

    best: dict | None = None
    best_score = 0
    for asset in release.get("assets", []):
        name = (asset.get("name") or "").lower()
        if not name or name.endswith(_NON_BINARY_SUFFIXES):
            continue
        if any(bad in name for bad in exclude):
            continue

        # Reject assets that name a different OS/arch than the one we want.
        if any(tok in name for tok in _ALL_OS_TOKENS) and not any(tok in name for tok in os_tokens):
            continue
        if any(tok in name for tok in _ALL_ARCH_TOKENS) and not any(tok in name for tok in arch_tokens):
            continue

        score = 1
        if any(tok in name for tok in os_tokens):
            score += 2
        if any(tok in name for tok in arch_tokens):
            score += 2
        score += sum(1 for hint in include if hint.lower() in name)
        # Prefer gnu over musl when both are published, all else equal.
        if "gnu" in name:
            score += 1

        if score > best_score:
            best, best_score = asset, score

    return best
