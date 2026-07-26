# HAProxy

Installs [HAProxy](https://www.haproxy.org) at a pinned minor version and prepares it for certificate management.

**Rune:** `haproxy` - **Active when:** `install = true` - **Default:** off

## What it deploys

- **Debian** - the [haproxy.debian.net](https://haproxy.debian.net) backports repository for the configured version (Debian 12 and 13 supported).
- **Ubuntu** - the `vbernat` HAProxy PPA for the configured version.
- **RHEL-family** - the distro's own HAProxy (the version pin does not apply; a warning is logged).
- A PKI directory at `/usr/local/etc/haproxy/pki` for ACME-issued certificates.
- When [`users.manage`](users.md) is on, grants the managed user ACL access to `/etc/haproxy` and the PKI directory, so certificate tooling can run unprivileged.

!!! note "Bring your own haproxy.cfg"

    NullForge installs and prepares HAProxy but does not manage `haproxy.cfg` - load-balancer configuration is yours (hand-written, ACME hooks, or a [custom rune](../guides/custom-runes.md)).

## Configuration (`features.haproxy`)

| Field | Default | Description |
| --- | --- | --- |
| `install` | `false` | Install HAProxy |
| `version` | `"3.2"` | Minor version for the Debian/Ubuntu repositories |

## Example

```python
from nullforge.molds import HaproxyMold

haproxy = HaproxyMold(install=True, version="3.2")
```
