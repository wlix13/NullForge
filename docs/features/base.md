# Base system

The `prepare` and `base` runes are not optional features - every full cast runs them first.
They are configured through the host's `system` data (`SystemMold`), not through `features`.

## prepare

Bootstraps a minimal image so the rest of the cast can rely on `sudo`:

- When connected as root, refreshes the package index and installs `sudo` and `locales`.

Fresh images without `sudo`: use [`--with-prepare`](../getting-started/cli.md#stages).

## base

Deploys the system baseline, in order:

1. **IPv6 stack** - when `ensure_ipv6` is set and GRUB carries `ipv6.disable=...`, strips it and regenerates the GRUB config (Debian `update-grub` or RHEL `grub2-mkconfig`).
2. **Hostname** - sets the hostname, writes it to `/etc/hosts` with the host's primary IP, and pins `preserve_hostname: true` in cloud-init so reboots keep it.
3. **Packages** - refreshes and upgrades, then installs `packages_base` (names are [mapped per distro](../concepts/architecture.md)).
4. **curl** - installs a pinned static `curl` to `/usr/local/bin` (removing the distro package on Debian, symlinking the CA bundle path on RHEL); falls back to the repo package when no static build fits the architecture.
5. **doggo** - a pinned DNS client for debugging resolvers.
6. **Locales** - resolves each requested locale against what the target can generate, enables it in `/etc/locale.gen`, and runs `locale-gen` when needed.
7. **Timezone** and **NTP** - `systemd-timesyncd` on Debian/Ubuntu, `chrony` (with a forced initial sync) on RHEL.
8. **Swap** - see below.

## Configuration (`system`)

| Field | Default | Description |
| --- | --- | --- |
| `packages_base` | curated list (~30 tools) | System-wide base packages: build toolchain, `git`, `jq`, `btop`, `nmap`, `zsh`, ... |
| `locales` | `["en_US.UTF-8 UTF-8"]` | Locales to generate |
| `timezone` | `"Etc/UTC"` | System timezone |
| `hostname` | `None` | FQDN; `None` leaves the hostname untouched |
| `swap` | see below | Swap configuration |
| `ensure_ipv6` | `true` | Repair a GRUB-disabled IPv6 kernel stack |

`hostname` is validated as a proper FQDN (labels, length, charset) at plan time.

### Swap (`system.swap`)

| Field | Default | Description |
| --- | --- | --- |
| `enabled` | `false` | Disabled removes both the swapfile and zram |
| `type` | `"zram"` | `"zram"` (compressed RAM) or `"basic"` (swapfile) |
| `algo` | `"zstd"` | zram compression: `"zstd"` or `"lzo"` |
| `size` | `"60%"` | `"4G"`, `"512M"`, or a percentage of RAM for zram |
| `swappiness` | `70` | `vm.swappiness`, persisted to `/etc/sysctl.d/` |

The two types are mutually exclusive - enabling one dismantles the other, so switching types in the inventory converges cleanly.

!!! note "swappiness vs netsec"

    [Network security](netsec.md) also sets `vm.swappiness` (default `10`) in its sysctl group.
    With swap enabled, the swap value is the effective one - its sysctl file sorts later; keep the two intentionally aligned.

## Example

```python
from nullforge.molds.defaults import BASE_SYSTEM
from nullforge.molds.utils import merge_system

system = merge_system(
    BASE_SYSTEM,
    {
        "hostname": "node1.example.com",
        "timezone": "Europe/Amsterdam",
        "swap": {"enabled": True, "size": "50%"},
    },
)
```
