# Xray

Installs [Xray-core](https://github.com/XTLS/Xray-core) with fresh geo data, ready for your own configuration.

**Rune:** `xray` - **Active when:** `install = true` - **Default:** off

## What it deploys

- Xray-core via the official [Xray-install](https://github.com/XTLS/Xray-install) script (`--beta` channel), skipped when `/usr/local/bin/xray` exists.
- `geoip.dat` / `geosite.dat` from [Loyalsoldier/v2ray-rules-dat](https://github.com/Loyalsoldier/v2ray-rules-dat) into `/usr/local/share/xray` - downloaded only when missing; delete the files to pull fresh data on the next cast.
- Ensures the `xray` service is running and enabled.
- When [`users.manage`](users.md) is on, grants the managed user ACL access to `/usr/local/share/xray` and `/usr/local/etc/xray` (including `config.json`), so proxy config can be managed without root.

!!! note "Bring your own config"

    `config.json` is not managed - inbounds, outbounds and routing are yours to deploy (by hand, from your tooling, or via a [custom rune](../guides/custom-runes.md)).

## Configuration (`features.xray`)

| Field | Default | Description |
| --- | --- | --- |
| `install` | `false` | Install Xray-core |

## Example

```python
from nullforge.molds import XrayCoreMold

xray = XrayCoreMold(install=True)
```
