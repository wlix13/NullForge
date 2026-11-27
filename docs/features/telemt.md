# Telemt

An MTProto proxy for Telegram via [telemt](https://github.com/telemt/telemt), with Fake-TLS masking, optional WARP egress, and a SYN-flood mitigation.

**Rune:** `telemt` - **Active when:** `install = true` - **Default:** off

## What it deploys

- The pinned `telemt` binary, run as a dedicated `telemt` service user.
- `/etc/telemt/telemt.toml` (mode `0640`) rendered from the mold - modes, users, network preferences, timeouts.
- A systemd unit. With `route_via_warp` (and [WARP](warp.md) active), a per-uid policy-routing helper sends Telegram-bound egress through the WARP interface, and the unit orders itself after the WARP service.
- With `synfix` set, a MEKO-style fix helper re-applies its rules on every (re)start via `ExecStartPre`/`ExecStopPost`.
- The value picks the variant.
- `v2`/`v3` insert `RETURN` rules ahead of the firewall so they coexist with UFW/firewalld.
- `v4` manages its own nftables queue table and a daemonized `nfqws2` (zapret2) instead of any SYN limit.

## Fake-TLS and the post-quantum check

In Fake-TLS mode (`ee`-links) the proxy masquerades as `tls_domain`.

Telegram's iOS client expects the masking domain to negotiate **X25519MLKEM768** hybrid post-quantum key exchange.
Domains that fall back to plain X25519 are observed to get proxies blocked for iOS users.

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
| `synfix` | `None` | MEKO MTProto fix variant ([MTPROTO_FIX_By_MEKO](https://github.com/Mekotofeuka/MTPROTO_FIX_By_MEKO)), `None` disables: `v2` rate-limits SYNs per source IP with an iOS bypass via TTL+Length; `v3` detects iOS by u32 TCP fingerprint (mark in mangle/PREROUTING) instead, for paths where load balancers break TTL/length; `v4` runs zapret2 `nfqws2` desync (window clamp + disorder/badsum) with no SYN limit - note clients whose own router runs zapret cannot connect to a v4 proxy |
| `mode_web` | `false` | Enable [WEB proxy mode](#web-proxy-mode) (`tg://webproxy` links) behind a Caddy TLS front; requires `web_host` and a non-443 MTProto `port` |
| `web_host` | `""` | Public FQDN of the WEB TLS front; its DNS record must point at this host |
| `web_public_addr` | resolved from `web_host` at plan time on control node | Literal `ip:port` for `web.vhosts.public_addr`; telemt rejects hostnames there, so an empty value resolves `web_host` at plan time on the control node |
| `web_base_path` | `""` | Optional URL subtree for the WEB vhost (slash-separated segments, empty = whole vhost) |
| `web_port` | `18080` | Loopback port of the WEB listener the front proxies to (TCP only; telemt WEB listeners do not support unix sockets) |
| `web_carrier` | `https` | WEB carrier (see `TelemtWebCarrier`) |
| `web_user` | all users | Limit the WEB vhost to this single access user; empty renders one WEB profile per entry in `users` (one `tg://webproxy` link each, `dd`-prefixed) |
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
    synfix="v3",
)
```

Generate secrets with `openssl rand -hex 16`.

## WEB proxy mode

With `mode_web` set, telemt additionally runs a loopback WEB listener (`transport = "web"`, default `web_port` 18080).
NullForge deploys a pinned [Caddy](https://caddyserver.com) on port 443 as the TLS front.
Caddy owns the certificate (automatic HTTPS) for `web_host` and forwards plain HTTP/1.1 to the WEB listener.
A loopback decoy site answers ordinary requests.
Clients use `tg://webproxy?server=<host>&secret=...` links (printed at telemt startup).
Telegram Desktop's WEB proxy type carries these as ordinary HTTPS/WebSocket - no MTProto handshake on the wire to fingerprint.

Constraints:

- `web_host` must be a dedicated FQDN whose DNS record points at this host, because Caddy gets a real certificate for it.
- The MTProto listener `port` must not be 443 (Caddy owns it) - use the default 8443.
- The mold rejects `port = 443` with `mode_web` set.
- WEB mode supports `plain` and `dd` secrets only (`ee`/Fake-TLS is not supported).
- NullForge hardcodes `dd` for padding/obfuscation, the recommended form, because plain is encapsulated in HTTPS anyway.
- With several MTProto groups, leave `web_user` empty: each user in `users` gets its own WEB profile and its own `tg://webproxy?server=<host>&secret=dd<secret>` link.
- Profile quotas are fixed (8 sessions / 512 streams / 64 per session).
- iOS clients support only the `https` carrier (the default).
- telemt WEB listeners are TCP-only: `[[server.listeners]]` has no unix-socket field, and `server.listen_unix_sock` applies to the main MTProto listener only.
- The front reaches telemt over loopback TCP on `web_port`.
- Caddy 2.10+ negotiates X25519MLKEM768 by default, so the real TLS endpoint is post-quantum.
- The `pq_check` on `tls_domain` still applies to the Fake-TLS ee links.
- When [netsec](netsec.md) is active, the operator must allow TCP 443 (and TCP 80 if using HTTP-01 ACME challenges) in `firewall_rules`.
- The telemt rune runs after netsec and cannot inject rules automatically.
- The decoy site is served by telemt itself from `/var/www/telemt-decoy` via the static_directory vhost mode.
