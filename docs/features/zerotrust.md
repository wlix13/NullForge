# Zero Trust Tunnel

Publishes services through a [Cloudflare Tunnel](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/) (`cloudflared`) without opening inbound ports.

**Rune:** `zerotrust` - **Active when:** `install = true` - **Default:** off

## What it deploys

- The pinned `cloudflared` binary, run as a dedicated `cloudflare` service user.
- `/etc/cloudflare/tunnel.yml` (mode `0600`) with the tunnel token, protocol, HA connection count, and post-quantum setting.
- A `cloudflare-tunnel` systemd unit; with `route_through_warp`, a helper script routes tunnel traffic out through the [WARP](warp.md) interface and the unit orders itself after the WARP service.
- Restarts only when the binary, config, unit, or routing script changed.

Create the tunnel and copy its token from the Cloudflare Zero Trust dashboard (or `cloudflared tunnel create`); NullForge runs the connector, it does not create tunnels.

## Configuration (`features.zerotrust`)

| Field | Default | Description |
| --- | --- | --- |
| `install` | `false` | Deploy the tunnel connector |
| `token` | `None` | Tunnel token - **required** when installing; redacted in debug output |
| `protocol` | `"auto"` | `auto`, `quic`, or `http2` |
| `post_quantum` | `false` | Post-quantum key agreement (QUIC only) |
| `ha_connections` | `2` | High-availability connections (1-4) |
| `route_through_warp` | `false` | Egress the tunnel through the WARP interface |

Validation rejects impossible combinations at plan time: installing without a token, post-quantum over HTTP/2, and post-quantum together with WARP routing.

`route_through_warp` assumes [WARP](warp.md) is active on the same host - its interface and service names are read from `features.warp`.

## Example

```python
from nullforge.molds import ZeroTrustTunnelMold

zerotrust = ZeroTrustTunnelMold(
    install=True,
    token="eyJhIjo...",
    post_quantum=True,
)
```
