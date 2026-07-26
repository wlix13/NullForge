# Tor

A local [Tor](https://www.torproject.org) SOCKS proxy with DNS resolution.

**Rune:** `tor` - **Active when:** `install = true` - **Default:** off

## What it deploys

- The distro's `tor` package.
- A rendered `/etc/tor/torrc` exposing a SOCKS listener and a DNSPort.
- Restarts Tor only when the config changed; always ensures the service is running and enabled.

The listeners bind locally - combine with your own firewall rules if you need to expose them.

## Configuration (`features.tor`)

| Field | Default | Description |
| --- | --- | --- |
| `install` | `false` | Install the Tor proxy |
| `socks_port` | `9050` | SOCKS5 listener port |
| `dns_port` | `5353` | DNS-over-Tor listener port |

## Example

```python
from nullforge.molds import TorMold

tor = TorMold(install=True)
```
