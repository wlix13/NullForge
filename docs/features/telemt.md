# Telemt

An MTProto proxy for Telegram via [telemt](https://github.com/telemt/telemt), with Fake-TLS masking, optional WARP egress, and a SYN-flood mitigation.

**Rune:** `telemt` - **Active when:** `install = true` - **Default:** off

## What it deploys

- The pinned `telemt` binary, run as a dedicated `telemt` service user.
- `/etc/telemt/telemt.toml` (mode `0640`) rendered from the mold - modes, users, network preferences, timeouts.
- A systemd unit; with `route_via_warp` (and [WARP](warp.md) active), a per-uid policy-routing helper sends Telegram-bound egress through the WARP interface, and the unit orders itself after the WARP service.
- With `synfix`, an iptables helper that re-applies a SYN rate-limiting chain on every (re)start; it inserts `RETURN` rules ahead of the firewall, so it coexists with UFW/firewalld.
- Restarts only when the binary, config, unit, or helper scripts changed.

## Fake-TLS and the post-quantum check

In Fake-TLS mode (`ee`-links) the proxy masquerades as `tls_domain`.
Telegram's iOS client expects the masking domain to negotiate **X25519MLKEM768** hybrid post-quantum key exchange; domains that fall back to plain X25519 are observed to get proxies blocked for iOS users.

With `pq_check` on (default), the domain is probed at plan time from the control node and the verdict is logged - pick a masking domain that offers X25519MLKEM768.

## Configuration (`features.telemt`)

| Field | Default | Description |
| --- | --- | --- |
| `install` | `false` | Install the proxy |
| `port` | `8443` | TCP listener port |
| `tls_domain` | `""` | Fake-TLS masking domain; required when `mode_tls` is on |
| `users` | `{}` | `username -> 32-hex-char secret`; at least one required; redacted in debug output |
| `mode_tls` | `true` | Fake-TLS (`ee`-prefixed) mode |
| `mode_secure` | `false` | Secure (`dd`-prefixed) mode |
| `mode_classic` | `false` | Classic unobfuscated mode |
| `route_via_warp` | `false` | Route Telegram egress through [WARP](warp.md) (per-uid policy routing) |
| `synfix` | `false` | Apply the MEKO SYN rate-limiting fix |
| `pq_check` | `true` | Vet `tls_domain` for post-quantum support at deploy time |
| `max_connections` | `16384` | Concurrent client connections |
| `client_handshake` | `30` | Client handshake timeout, seconds |
| `fast_mode` | `true` | telemt fast mode |
| `use_middle_proxy` | `false` | Route via Telegram middle proxies (enables ad tags) |
| `ipv6` | `true` | Allow IPv6 upstream connections |
| `prefer` | `6` | Preferred address family (`4` or `6`) |
| `api_enabled` | `false` | Expose the local management/metrics API |
| `unknown_sni_action` | `None` | Handling of connections with an unexpected SNI |

Validation at plan time: at least one user, valid 32-hex secrets, at least one mode enabled, and a `tls_domain` whenever Fake-TLS is on.

## Example

```python
from nullforge.molds import TelemtMold

telemt = TelemtMold(
    install=True,
    port=443,
    tls_domain="cdn.example.com",
    users={"example": "bf777cca8384a074a671460d51e4e31f"},
    route_via_warp=True,
    synfix=True,
)
```

Generate secrets with `openssl rand -hex 16`.
