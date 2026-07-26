# DNS

Encrypted DNS resolution for the host itself.

**Rune:** `dns` - **Active when:** `mode != "none"` - **Default:** on (Blocky)

## Modes

| Mode | Transport | Resolver |
| --- | --- | --- |
| `blocky` (default) | DNS-over-HTTPS | [Blocky](https://0xerr0r.github.io/blocky/) proxy on a local interface |
| `dot_resolved` | DNS-over-TLS | systemd-resolved |
| `none` | - | feature disabled, resolver untouched |

Switching modes converges: `dot_resolved` stops and disables the Blocky services before configuring resolved.

### `blocky`

- Runs the pinned Blocky binary as a dedicated `blocky` service user.
- Binds to `listen_address` (default `169.254.0.53`).
  For a non-global, non-loopback address, a `dns-internal` oneshot service creates a dummy interface holding it - the resolver stays reachable regardless of external interface state.
  Wildcard and loopback addresses use existing interfaces.
- Renders `/etc/blocky/config.yaml` with DoH upstreams from the selected provider (IPv6 upstreams included only when the host has IPv6).
- Points `/etc/resolv.conf` directly at the Blocky address, replacing any symlink.
- Restarts Blocky only when the binary, config, or unit changed.

### `dot_resolved`

- Configures `/etc/systemd/resolved.conf` with DoT upstreams (`address#SNI` form) from the selected provider.
- Links `/etc/resolv.conf` to the resolved stub and flushes caches on change.

## Providers

| Provider | DoH (blocky) | DoT (dot_resolved) | ECS |
| --- | --- | --- | --- |
| `cloudflare` (default) | 1.1.1.1 / 1.0.0.1 | `cloudflare-dns.com` | - |
| `google` | 8.8.8.8 / 8.8.4.4 | `dns.google` | - |
| `quad9` | 9.9.9.10/.12 | `dns10/dns11.quad9.net` | yes |

`ecs = true` (EDNS Client Subnet) selects Quad9's ECS-enabled endpoints and is rejected for other providers.

## Configuration (`features.dns`)

| Field | Default | Description |
| --- | --- | --- |
| `mode` | `"blocky"` | `blocky`, `dot_resolved`, or `none` |
| `upstream_provider` | `"cloudflare"` | `cloudflare`, `google`, `quad9` |
| `ecs` | `false` | ECS endpoints (Quad9 only) |
| `listen_address` | `169.254.0.53` | Blocky bind address; wildcard/loopback/non-global only |

## Example

```python
from nullforge.models.dns import DnsMode, DnsProvider
from nullforge.molds import DnsMold

dns = DnsMold(mode=DnsMode.BLOCKY, upstream_provider=DnsProvider.QUAD9, ecs=True)
```
