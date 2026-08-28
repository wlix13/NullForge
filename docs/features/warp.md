# Cloudflare WARP

Egress through [Cloudflare WARP](https://developers.cloudflare.com/warp-client/), as a routing building block for other features.

**Rune:** `warp` - **Active when:** `install = true` - **Default:** off

WARP gives the host a Cloudflare-terminated tunnel interface without changing the default route - nothing is routed through it until something opts in ([Telemt](telemt.md) per-uid routing, [Zero Trust Tunnel](zerotrust.md) `route_through_warp`, or your own policy rules).

## Engines

| | `masque` (default) | `wireguard` |
| --- | --- | --- |
| Client | [usque](https://github.com/Diniboy1123/usque) (MASQUE / HTTP3) | [wgcf](https://github.com/ViRb3/wgcf) profile + kernel WireGuard |
| Service | `cloudflare-warp` | `wg-quick@warp` |
| Config | `/etc/usque/config.json` | `/etc/wgcf/`, linked to `/etc/wireguard/warp.conf` |

### masque

- Installs the pinned `usque` binary and enrolls/registers the device on first run (config file is the marker - an existing registration is reused).
- Deploys an IPv6 policy script and a systemd unit that brings up the interface with the configured name and MTU; outbound IPv6 is used only when the host has connectivity beside the WARP interface itself.
- Restarts only when the binary, script, or unit changed.

### wireguard

- Installs WireGuard packages and the pinned `wgcf` binary.
- Registers a WARP account and generates the profile on first run, then post-processes it: the `DNS` line is dropped (resolver stays under [DNS](dns.md) control) and `Table = off` is added so no default route is installed.
- Failed registration (rate limiting) skips the dependent steps instead of half-configuring; the next cast retries.

## Downloads through WARP

Every `curl` NullForge itself runs on the host - release binaries, installer scripts, geo databases - is probed at plan time with a one-byte request over the default route.
When that probe fails and WARP is active on the host, the probe is repeated through the WARP interface; if Cloudflare confirms the interface carries WARP egress, the download binds to it (`curl --interface`), so a filtered uplink that blocks GitHub or similar no longer breaks installs.

- The direct route always wins when it works: WARP is a fallback, never a detour.
- Decisions are cached per URL for the cast; facts are gathered before operations run, so a cast that installs WARP itself still downloads directly - the fallback is available from the next cast.
- Package managers, `git` clones, and downloads made from inside third-party install scripts (Docker, Xray, Nezha) are not affected.

## Configuration (`features.warp`)

| Field | Default | Description |
| --- | --- | --- |
| `install` | `false` | Deploy WARP |
| `engine_type` | `"masque"` | `masque` or `wireguard` |
| `iface` | `"warp"` | Tunnel interface name |
| `mtu` | `1280` | Interface MTU (1280-9216) |
| `zero_trust` | `false` | Zero Trust enrollment - not implemented yet, must stay `false` |

## Example

```python
from nullforge.molds import WarpMold

warp = WarpMold(install=True, iface="warp0")
```
