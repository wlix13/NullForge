"""Network security and hardening configuration mold."""

from ipaddress import IPv6Network, ip_network
from typing import Literal

from pydantic import Field, field_validator

from nullforge.models.netsec import SshHostKeyType

from .base_mold import BaseMold


SSH_PORT = 22
"""Default SSH port."""


class SshMold(BaseMold):
    """SSH daemon key material and key-exchange configuration."""

    host_keys: list[SshHostKeyType] | None = Field(
        default=None,
        description="Host key types sshd offers, one HostKey directive per entry. "
        "None keeps distro default set; missing key files are generated.",
    )
    pq_kex_priority: bool = Field(
        default=True,
        description="Prefer post-quantum hybrid key exchange by prepending PQ algorithms",
    )
    strip_weak_algorithms: bool = Field(
        default=True,
        description="Remove weak algorithms from the sshd offer and sub-3072-bit DH group-exchange moduli.",
    )

    @field_validator("host_keys")
    @classmethod
    def _validate_host_keys(cls, value: list[SshHostKeyType] | None) -> list[SshHostKeyType] | None:
        if value is None:
            return value
        if not value:
            raise ValueError("host_keys cannot be empty: sshd needs at least one host key (use None for defaults)")
        return list(dict.fromkeys(value))


class FirewallRule(BaseMold):
    """A single UFW firewall rule, to ``ufw`` CLI invocation.

    Fields map directly to UFW command:
      ufw ACTION [DIRECTION] [on IFACE] [proto PROTO]
          from FROM_IP to TO_IP [port PORT] [comment "COMMENT"]
    """

    port: int | str | None = Field(
        default=None,
        description="Port number (22), range string ('8080:8090'), or None for IP-only rules",
    )
    proto: Literal["tcp", "udp", "any"] = Field(
        default="any",
        description="Protocol to match; 'any' omits the proto clause entirely",
    )
    from_ip: str | None = Field(
        default=None,
        description="Source IP address or CIDR (IPv4 or IPv6). None resolves to 'any'",
    )
    to_ip: str | None = Field(
        default=None,
        description="Destination IP address or CIDR. None resolves to 'any'",
    )
    action: Literal["allow", "deny", "reject", "limit"] = Field(
        default="allow",
        description="UFW action to apply",
    )
    direction: Literal["in", "out"] | None = Field(
        default=None,
        description="Traffic direction; None lets UFW apply its default (in)",
    )
    interface: str | None = Field(
        default=None,
        description="Bind rule to a specific network interface, e.g. 'eth0'",
    )
    comment: str | None = Field(
        default=None,
        description="Optional label stored in UFW rule metadata",
    )

    @property
    def is_ipv6(self) -> bool:
        """True when this rule references IPv6 address exclusively.

        Rules where from_ip and to_ip are None are considered protocol-agnostic
        and are not classified as IPv6-only. Mixed rules that reference both IPv4
        and IPv6 address are also not IPv6-only.
        """

        candidates = [a for a in (self.from_ip, self.to_ip) if a and a not in ("any", "anywhere")]
        if not candidates:
            return False
        try:
            networks = [ip_network(addr, strict=False) for addr in candidates]
        except ValueError:
            return False
        return all(isinstance(net, IPv6Network) for net in networks)


def _default_firewall_rules() -> list[FirewallRule]:
    """Default UFW ruleset — allow SSH from anywhere."""

    return [FirewallRule(port=SSH_PORT, comment="SSH")]


def _default_system_sysctl() -> dict[str, int]:
    """Get the default sysctl parameters."""

    sysctl = {
        # --- SYSTEM RESOURCE LIMITS ---
        "fs.nr_open": 3000000,
        "fs.file-max": 2097152,
        "vm.swappiness": 10,
    }

    return sysctl


def _default_conntrack_sysctl() -> dict[str, int]:
    """Get the default sysctl parameters for conntrack."""

    return {
        # --- TCP TIMEOUTS ---
        "net.netfilter.nf_conntrack_tcp_timeout_established": 3600,  # default 432000
        "net.netfilter.nf_conntrack_tcp_timeout_time_wait": 30,
        "net.netfilter.nf_conntrack_tcp_timeout_close_wait": 30,
        "net.netfilter.nf_conntrack_generic_timeout": 120,
        # --- UDP TIMEOUTS ---
        "net.netfilter.nf_conntrack_udp_timeout": 30,
        "net.netfilter.nf_conntrack_udp_timeout_stream": 120,
    }


def _default_ipv4_sysctl() -> dict[str, str | int]:
    """Get the default sysctl parameters for IPv4 stack."""

    net_sysctl = {
        # --- ROUTING & CORE ---
        "net.ipv4.conf.all.rp_filter": 2,
        "net.ipv4.conf.default.rp_filter": 2,
        "net.core.default_qdisc": "fq",
        "net.ipv4.tcp_congestion_control": "bbr",
        # --- BACKLOGS ---
        "net.core.somaxconn": 65535,
        "net.core.netdev_max_backlog": 65535,
        "net.ipv4.tcp_max_syn_backlog": 65535,
        # --- PORT MANAGEMENT ---
        "net.ipv4.ip_local_port_range": "15000 60999",
        "net.ipv4.tcp_tw_reuse": 1,
        "net.ipv4.tcp_fin_timeout": 30,
        # --- MEMORY BUFFERS ---
        "net.core.optmem_max": 65536,
        "net.core.rmem_default": 262144,
        "net.core.wmem_default": 262144,
        "net.core.rmem_max": 67108864,
        "net.core.wmem_max": 67108864,
        "net.ipv4.tcp_rmem": "4096 87380 67108864",
        "net.ipv4.tcp_wmem": "4096 65536 67108864",
        "net.ipv4.udp_rmem_min": 16384,
        "net.ipv4.udp_wmem_min": 16384,
        # --- TCP FEATURES ---
        "net.ipv4.tcp_mtu_probing": 1,
        "net.ipv4.tcp_slow_start_after_idle": 0,
        "net.ipv4.tcp_keepalive_time": 600,
        "net.ipv4.tcp_keepalive_intvl": 30,
        "net.ipv4.tcp_keepalive_probes": 3,
        "net.ipv4.tcp_syncookies": 1,
        "net.ipv4.tcp_fastopen": 3,
        "net.ipv4.tcp_notsent_lowat": 16384,
    }

    return net_sysctl


def _default_ipv6_sysctl() -> dict[str, int]:
    """Get the default sysctl parameters for IPv6 stack."""

    net_sysctl = {
        # --- NEIGHBOR DISCOVERY ---
        "net.ipv6.neigh.default.gc_thresh1": 128,
        "net.ipv6.neigh.default.gc_thresh2": 512,
        "net.ipv6.neigh.default.gc_thresh3": 4096,
        # --- BINDING ---
        "net.ipv6.bindv6only": 0,
    }

    return net_sysctl


class NetSecMold(BaseMold):
    """Full network configuration mold."""

    install: bool = Field(
        default=True,
        description="Whether to apply network security and hardening",
    )
    firewall: bool = Field(
        default=True,
        description="Whether to enable firewall (UFW on Debian/Ubuntu, firewalld on RHEL)",
    )
    firewall_rules: list[FirewallRule] = Field(
        default_factory=_default_firewall_rules,
        description="Ordered list of firewall rules to apply. Rules with IPv6 addresses "
        "are automatically skipped on hosts without IPv6 connectivity.",
    )
    ssh: SshMold = Field(
        default_factory=SshMold,
        description="SSH daemon host key and key-exchange configuration",
    )
    system_sysctl: dict[str, int] | None = Field(
        default_factory=_default_system_sysctl,
        description="Sysctl parameters to apply",
    )
    conntrack_sysctl: dict[str, int] | None = Field(
        default_factory=_default_conntrack_sysctl,
        description="Conntrack sysctl parameters to apply",
    )
    ipv4_sysctl: dict[str, str | int] | None = Field(
        default_factory=_default_ipv4_sysctl,
        description="IPv4 sysctl parameters to apply",
    )
    ipv6_sysctl: dict[str, int] | None = Field(
        default_factory=_default_ipv6_sysctl,
        description="IPv6 sysctl parameters to apply",
    )
    reinstall: bool = Field(
        default=False,
        description="Whether to force reconfigure the firewall even if already active",
    )

    @property
    def is_active(self) -> bool:
        return self.install
