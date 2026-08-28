# Version pinning

Tools that NullForge installs from release archives are pinned, not `latest`.
A cast converges every host to the pin; bumping a pin re-installs on the next cast.

## Default pins

`DEFAULT_VERSIONS` in `nullforge/smithy/versions.py`:

| Tool | Used by |
| --- | --- |
| `curl`, `doggo` | [base](../features/base.md) |
| `eza`, `tmux`, `nvim`, `direnv`, `nerd_fonts` | [profiles](../features/profiles.md) |
| `usque`, `wgcf` | [WARP](../features/warp.md) |
| `cloudflared` | [Zero Trust Tunnel](../features/zerotrust.md) |
| `blocky` | [DNS](../features/dns.md) |
| `telemt` | [Telemt](../features/telemt.md) |

Run `nullforge runes` from a checkout - or read the file - for the exact current pins.

## Overriding per host

Inventory data key `versions` overlays the defaults:

```python
hosts = [
    (
        "203.0.113.10",
        {
            "system": ...,
            "features": ...,
            "versions": {"blocky": "v0.34.0", "tmux": "3.7b"},
        },
    ),
]
```

Most tools also accept `"latest"`, which resolves GitHub's latest-release URL.

!!! warning "`latest` weakens convergence"

    With `latest`, the guard reduces to "binary exists" - the host stops converging to a known version, and tools whose asset names embed the version (blocky, wgcf, usque, doggo, tmux, curl) will 404 on `latest`.
    Prefer explicit pins.

## How the guard works

Installers check `is_pinned_version_installed(tool, binary_path)` before doing anything:

1. The binary must exist.
2. The tool's version command (`eza --version`, `blocky version`, ...) must report the pinned version.
   Tools with no version output (`wgcf`) are tracked through marker files under `/var/lib/nullforge/versions`.

Only when the guard fails does the installer download - which is also when the release's sha256 is resolved from GitHub metadata on the control node and verified on the target.
Checksum resolution is best-effort: a repo that publishes no checksums installs unverified (a warning is logged).
The download falls back to the [WARP interface](../features/warp.md#downloads-through-warp) when the direct route is filtered and the host has WARP.

## Not pin-driven

Some installs deliberately sit outside the pin system: script-based installers (Docker, starship, zoxide, atuin, Xray, Nezha) and distro packages (Tor, HAProxy - which has its own [`version` field](../features/haproxy.md)).
These are guarded by presence, not version.
