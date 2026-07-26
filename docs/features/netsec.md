# Network security

SSH hardening, a default-deny firewall, and kernel network tuning.

**Rune:** `netsec` - **Active when:** `install = true` - **Default:** on

## SSH hardening

Directives edited in `/etc/ssh/sshd_config`:

- `PasswordAuthentication no` - only when [`users.manage`](users.md) is true; keep one of the user's [SSH key sources](users.md) enabled or the host becomes unreachable over SSH.
- `PermitRootLogin no`
- `UseDNS yes`

Key material and key exchange go into a drop-in at `/etc/ssh/sshd_config.d/40-nullforge.conf`, sorted before distro drop-ins so its directives win:

- **Host keys** - when `ssh.host_keys` is set, only those `HostKey` directives are offered (missing key files are generated) along with matching `HostKeyAlgorithms`.
- **Post-quantum KEX** - with `pq_kex_priority`, hybrid PQ algorithms (`mlkem768x25519-sha256`, `sntrup761x25519-sha512`) are preferred ahead of strong classical ones, filtered to what the target's OpenSSH supports.
- **Weak-algorithm stripping** - with `strip_weak_algorithms`, weak KEX patterns, weak MACs, and `ssh-rsa` CA signatures are removed, and sub-3072-bit DH group-exchange moduli are dropped from `/etc/ssh/moduli`.

Every config change is validated with `sshd -t` before the daemon restarts; the restart only happens when something actually changed, so re-casts never bounce sshd.

## Firewall

UFW on Debian/Ubuntu, firewalld on RHEL.
The desired ruleset is fingerprinted (order-independent SHA-256, persisted on the host); when the fingerprint matches and the firewall is active, the whole section is skipped.
On any rule change the ruleset is reset and reapplied from scratch - the inventory is the single source of truth, and rules added by hand are wiped.

Default policies: **incoming denied**, outgoing allowed, plus one rule allowing SSH on port 22.
UFW additionally sets its forward policy to allow; firewalld keeps its own forwarding defaults.

Rules with IPv6 addresses are silently skipped on hosts without IPv6 connectivity.

### Rule fields (`features.netsec.firewall_rules[]`)

| Field | Default | Description |
| --- | --- | --- |
| `port` | `None` | Port (`22`), range (`"8080:8090"`), or `None` for IP-only rules |
| `proto` | `"any"` | `tcp`, `udp`, or `any` |
| `from_ip` / `to_ip` | `None` | Address or CIDR; `None` means `any` |
| `action` | `"allow"` | `allow`, `deny`, `reject`, `limit` |
| `direction` | `None` | `in`, `out`, or firewall default |
| `interface` | `None` | Bind the rule to an interface |
| `comment` | `None` | Label stored in rule metadata |

!!! warning "firewalld limitations"

    `direction="out"` and `action="limit"` rules raise an error on RHEL - firewalld has no equivalents.
    Simple allows become `--add-port`; everything else becomes rich rules; the `public` zone target is set to `DROP`.

!!! warning "Replacing rules replaces the SSH rule too"

    A layer that sets `firewall_rules` replaces the whole default list.
    Keep an SSH rule in your custom set (on the right port) or you will lock yourself out on the next cast.

## Sysctl tuning

Four opinionated groups, each persisted to its own file under `/etc/sysctl.d/`:

| Group | Highlights |
| --- | --- |
| `system_sysctl` | file-handle limits, `vm.swappiness=10` |
| `conntrack_sysctl` | shortened TCP/UDP conntrack timeouts; `nf_conntrack_max` sized from RAM at deploy time (skipped when the module isn't loaded) |
| `ipv4_sysctl` | BBR + fq, large buffers and backlogs, TCP Fast Open, keepalive tuning |
| `ipv6_sysctl` | neighbor-table sizing; applied only when the host has IPv6 |

Set a group to `None` to skip it, or pass your own dict to replace it wholesale.

## Configuration (`features.netsec`)

| Field | Default | Description |
| --- | --- | --- |
| `install` | `true` | Apply the feature at all |
| `firewall` | `true` | Manage UFW/firewalld |
| `firewall_rules` | allow SSH/22 | Ordered rule list (see above) |
| `ssh.host_keys` | `None` (distro set) | Offered host key types: `ed25519`, `ecdsa`, `rsa` |
| `ssh.pq_kex_priority` | `true` | Prefer post-quantum hybrid KEX |
| `ssh.strip_weak_algorithms` | `true` | Strip weak KEX/MACs/moduli |
| `system_sysctl` / `conntrack_sysctl` / `ipv4_sysctl` / `ipv6_sysctl` | opinionated defaults | Per-group sysctl dicts, `None` to skip |
| `reinstall` | `false` | Force a firewall reset even when the fingerprint matches |

## Example

```python
from nullforge.molds import FirewallRule, NetSecMold
from nullforge.molds.defaults import BASE_FEATURES

rules = [
    *BASE_FEATURES.netsec.firewall_rules,  # keep the SSH rule
    FirewallRule(port=443, proto="tcp", comment="HTTPS"),
]

netsec = NetSecMold(
    firewall_rules=rules,
    ssh={"host_keys": ["ed25519"]},
)
```
