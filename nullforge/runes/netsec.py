"""Network security and hardening deployment module."""

import hashlib
import io
import json

from pyinfra.api.operation import OperationMeta
from pyinfra.context import host
from pyinfra.facts.files import File, FileContents
from pyinfra.facts.server import Command
from pyinfra.operations import files, server, systemd
from pyinfra.operations.util import any_changed

from nullforge.models.netsec import (
    CLASSICAL_KEX_ALGORITHMS,
    HOST_KEY_ALGORITHMS,
    MIN_DH_MODULUS_SIZE,
    PQ_KEX_ALGORITHMS,
    WEAK_KEX_PATTERNS,
    WEAK_MAC_PATTERNS,
)
from nullforge.molds import FeaturesMold, FirewallRule, NetSecMold, SshMold, UserMold
from nullforge.smithy.network import conntrack_max_for, has_ipv6, module_loaded
from nullforge.smithy.packages import get_pm
from nullforge.smithy.system import get_total_memory


SSHD_CONFIG_PATH = "/etc/ssh/sshd_config"
SSH_MODULI_PATH = "/etc/ssh/moduli"

SSHD_DROPIN_PATH = "/etc/ssh/sshd_config.d/40-nullforge.conf"
"""Sorted before distro drop-ins (50-redhat.conf, 50-cloud-init.conf) so first-obtained directives win."""


def _read_checksum_file(path: str) -> str:
    """Read checksum file, returning empty string when absent."""

    contents = host.get_fact(FileContents, path=path, _sudo=True)
    return contents[0].strip() if contents else ""


def deploy_network_security() -> None:
    """Deploy network security and hardening configuration."""

    features: FeaturesMold = host.data.features
    user_opts: UserMold = features.users
    netsec_opts: NetSecMold = features.netsec

    _enhance_ssh_daemon(user_opts, netsec_opts.ssh)

    if netsec_opts.firewall:
        pm = get_pm()
        if pm.is_rhel_based:
            _configure_firewalld_firewall(netsec_opts)
        else:
            _configure_ufw_firewall(netsec_opts)

    _apply_sysctl_tuning(netsec_opts)


def _rules_checksum(rules: list[FirewallRule]) -> str:
    """Compute a deterministic SHA-256 of the desired active ruleset.

    Rules are serialised as sorted JSON objects and then sorted themselves so
    order in inventory does not affect fingerprint. Any change to ruleset:
    add rule, remove rule, modify field will produces different hash,
    triggering a full UFW reset on next run.
    """

    fingerprints = sorted(json.dumps(r.model_dump(), sort_keys=True) for r in rules)
    payload = "\n".join(fingerprints)
    return hashlib.sha256(payload.encode()).hexdigest()


def _build_ufw_command(rule: FirewallRule) -> str:
    """Build complete `ufw` CLI command string from `FirewallRule`.

    Produces the canonical long-form command:
      ufw ACTION [DIRECTION] [on IFACE] [proto PROTO]
          from ADDR to ADDR [port PORT] [comment "LABEL"]
    """

    parts: list[str] = ["ufw", rule.action]

    if rule.direction:
        parts.append(rule.direction)

    if rule.interface:
        parts += ["on", rule.interface]

    if rule.proto != "any":
        parts += ["proto", rule.proto]

    parts += ["from", rule.from_ip or "any"]
    parts += ["to", rule.to_ip or "any"]

    if rule.port is not None:
        parts += ["port", str(rule.port)]

    if rule.comment:
        parts += ["comment", f'"{rule.comment}"']

    return " ".join(parts)


def _configure_ufw_firewall(opts: NetSecMold) -> None:
    """Configure UFW firewall with the specified rule set.

    IPv6-targeted rules (those whose source/destination is an IPv6 address or
    subnet) are silently dropped when the host has no IPv6 connectivity.
    """

    ipv6 = has_ipv6()
    active_rules = [r for r in opts.firewall_rules if ipv6 or not r.is_ipv6]
    checksum = _rules_checksum(active_rules)
    checksum_file = "/etc/ufw/.nullforge_checksum"

    pm = get_pm()
    pm.install(
        name="Install UFW firewall",
        packages=["ufw"],
        _sudo=True,
    )

    cmd_get_ufw = "ufw status 2>/dev/null || true"
    if not opts.reinstall:
        ufw_status = host.get_fact(Command, cmd_get_ufw, _sudo=True) or ""
        if "Status: active" in ufw_status and _read_checksum_file(checksum_file) == checksum:
            return

    server.shell(
        name="Reset UFW to clean state",
        commands=[
            "ufw --force reset",
        ],
        _sudo=True,
    )

    ipv6_value = "yes" if ipv6 else "no"
    server.shell(
        name=f"Configure UFW IPv6={ipv6_value}",
        commands=[
            f"sed -i 's/^IPV6=.*/IPV6={ipv6_value}/' /etc/default/ufw",
        ],
        _sudo=True,
    )

    server.shell(
        name="Set UFW default policies",
        commands=[
            "ufw default deny incoming",
            "ufw default allow outgoing",
            "ufw default allow forward",
        ],
        _sudo=True,
    )

    for rule in host.loop(active_rules):
        cmd = _build_ufw_command(rule)
        label = f"UFW {rule.action}: {rule.comment or cmd}"
        server.shell(
            name=label,
            commands=[cmd],
            _sudo=True,
        )

    server.shell(
        name="Enable UFW firewall",
        commands=[
            "yes | ufw enable",
        ],
        _sudo=True,
    )

    server.shell(
        name="Persist UFW ruleset checksum",
        commands=[
            f"printf '%s' '{checksum}' > {checksum_file}",
        ],
        _sudo=True,
    )


def _build_firewalld_commands(rule: FirewallRule) -> list[str]:
    """Build firewall-cmd command strings from a FirewallRule.

    Returns one or two commands depending on protocol.
    Raises ValueError for direction='out' and action='limit' rules (not supported on firewalld).
    """

    if rule.direction == "out":
        raise ValueError(
            f"direction='out' rules are not supported on firewalld (port={rule.port}, comment={rule.comment!r})"
        )

    if rule.action == "limit":
        raise ValueError(
            f"action='limit' rules are not supported on firewalld (port={rule.port}, comment={rule.comment!r})"
        )

    action_map = {"allow": "accept", "deny": "drop", "reject": "reject"}
    fw_action = action_map[rule.action]
    zone = "public"

    # Simple port-allow with no IP/interface constraints — use --add-port (cleaner)
    if (
        rule.action == "allow"
        and rule.from_ip is None
        and rule.to_ip is None
        and rule.interface is None
        and rule.port is not None
    ):
        if rule.proto == "any":
            return [
                f"firewall-cmd --permanent --zone={zone} --add-port={rule.port}/tcp",
                f"firewall-cmd --permanent --zone={zone} --add-port={rule.port}/udp",
            ]
        return [f"firewall-cmd --permanent --zone={zone} --add-port={rule.port}/{rule.proto}"]

    # Rich rule for all other cases
    def make_rich_rule(family: str, proto: str | None) -> str:
        parts = [f'rule family="{family}"']
        if rule.from_ip:
            parts.append(f'source address="{rule.from_ip}"')
        if rule.to_ip:
            parts.append(f'destination address="{rule.to_ip}"')
        if rule.port is not None and proto is not None:
            parts.append(f'port port="{rule.port}" protocol="{proto}"')
        parts.append(fw_action)
        return " ".join(parts)

    family = "ipv6" if rule.is_ipv6 else "ipv4"

    if rule.proto == "any" and rule.port is not None:
        return [
            f"firewall-cmd --permanent --zone={zone} --add-rich-rule='{make_rich_rule(family, 'tcp')}'",
            f"firewall-cmd --permanent --zone={zone} --add-rich-rule='{make_rich_rule(family, 'udp')}'",
        ]

    proto = rule.proto if rule.proto != "any" else None
    return [f"firewall-cmd --permanent --zone={zone} --add-rich-rule='{make_rich_rule(family, proto)}'"]


def _configure_firewalld_firewall(opts: NetSecMold) -> None:
    """Configure firewalld with the specified rule set.

    IPv6-targeted rules are silently dropped when the host has no IPv6 connectivity.
    direction='out' rules raise ValueError as egress control requires firewalld policy objects.
    action='limit' rules raise ValueError as firewalld has no equivalent of ufw's rate limiting.
    """

    ipv6 = has_ipv6()
    active_rules = [r for r in opts.firewall_rules if ipv6 or not r.is_ipv6]
    checksum = _rules_checksum(active_rules)
    checksum_file = "/etc/firewalld/.nullforge_checksum"

    pm = get_pm()
    pm.install(
        name="Install firewalld",
        packages=["firewalld"],
        _sudo=True,
    )

    systemd.service(
        name="Ensure firewalld is running and enabled",
        service="firewalld",
        running=True,
        enabled=True,
        _sudo=True,
    )

    if not opts.reinstall and _read_checksum_file(checksum_file) == checksum:
        return

    server.shell(
        name="Flush firewalld public zone rich rules",
        commands=[
            "firewall-cmd --permanent --zone=public --list-rich-rules"
            " | xargs -r -d '\\n' -I _RULE"
            " firewall-cmd --permanent --zone=public --remove-rich-rule=_RULE",
        ],
        _sudo=True,
    )

    server.shell(
        name="Flush firewalld public zone ports",
        commands=[
            "firewall-cmd --permanent --zone=public --list-ports"
            " | tr ' ' '\\n'"
            " | xargs -r -I _PORT"
            " firewall-cmd --permanent --zone=public --remove-port=_PORT",
        ],
        _sudo=True,
    )

    server.shell(
        name="Set firewalld default zone policy to DROP",
        commands=["firewall-cmd --permanent --zone=public --set-target=DROP"],
        _sudo=True,
    )

    for rule in host.loop(active_rules):
        cmds = _build_firewalld_commands(rule)
        label = f"firewalld {rule.action}: {rule.comment or rule.port}"
        server.shell(
            name=label,
            commands=cmds,
            _sudo=True,
        )

    server.shell(
        name="Reload firewalld",
        commands=["firewall-cmd --reload"],
        _sudo=True,
    )

    server.shell(
        name="Persist firewalld ruleset checksum",
        commands=[f"printf '%s' '{checksum}' > {checksum_file}"],
        _sudo=True,
    )


def _supported_kex_algorithms() -> frozenset[str]:
    raw = host.get_fact(Command, "ssh -Q kex 2>/dev/null || true") or ""
    return frozenset(line.strip() for line in raw.splitlines() if line.strip())


def _kex_directive(ssh_opts: SshMold, supported_kex: frozenset[str]) -> str | None:
    """Single KexAlgorithms value combining PQ priority and weak-algorithm removal."""

    pq = [algo for algo in PQ_KEX_ALGORITHMS if algo in supported_kex] if ssh_opts.pq_kex_priority else []

    if ssh_opts.strip_weak_algorithms:
        classical = [algo for algo in CLASSICAL_KEX_ALGORITHMS if algo in supported_kex]
        if pq and classical:
            return ",".join((*pq, *classical))
        return f"-{WEAK_KEX_PATTERNS}"

    if pq:
        return "^" + ",".join(pq)
    return None


def _build_sshd_dropin(ssh_opts: SshMold, supported_kex: frozenset[str]) -> str:
    """Prepare sshd drop-in file content."""

    lines = [f"HostKey /etc/ssh/ssh_host_{key_type}_key" for key_type in ssh_opts.host_keys or []]
    if ssh_opts.host_keys:
        offered = [algo for key_type in ssh_opts.host_keys for algo in HOST_KEY_ALGORITHMS[key_type]]
        lines.append("HostKeyAlgorithms " + ",".join(offered))

    kex = _kex_directive(ssh_opts, supported_kex)
    if kex:
        lines.append(f"KexAlgorithms {kex}")

    if ssh_opts.strip_weak_algorithms:
        lines.append(f"MACs -{WEAK_MAC_PATTERNS}")
        lines.append("CASignatureAlgorithms -ssh-rsa")

    if not lines:
        return ""

    header = "# Managed by NullForge - do not edit, changes are overwritten on deploy."
    return "\n".join([header, *lines]) + "\n"


def _configure_sshd_dropin(ssh_opts: SshMold) -> list[OperationMeta]:
    """Deploy sshd drop-in pinning offered host keys and key-exchange priority."""

    content = _build_sshd_dropin(
        ssh_opts,
        _supported_kex_algorithms(),
    )

    if not content:
        return [
            files.file(
                name="Remove sshd drop-in",
                path=SSHD_DROPIN_PATH,
                present=False,
                _sudo=True,
            )
        ]

    ops: list[OperationMeta] = []

    for key_type in host.loop(ssh_opts.host_keys or []):
        key_path = f"/etc/ssh/ssh_host_{key_type}_key"
        if host.get_fact(File, path=key_path, _sudo=True):
            continue
        ops.append(
            server.shell(
                name=f"Generate {key_type} host key",
                commands=[f"ssh-keygen -q -t {key_type} -f {key_path} -N ''"],
                _sudo=True,
            )
        )

    ops.append(
        files.line(
            name="Include drop-in directory",
            path=SSHD_CONFIG_PATH,
            line=r"^[[:space:]]*Include[[:space:]]+/etc/ssh/sshd_config\.d/\*\.conf",
            replace="Include /etc/ssh/sshd_config.d/*.conf",
            extended_regex=True,
            _sudo=True,
        )
    )
    ops.append(
        files.put(
            name="Configure sshd drop-in",
            src=io.StringIO(content),
            dest=SSHD_DROPIN_PATH,
            mode="0600",
            create_remote_dir=True,
            _sudo=True,
        )
    )
    return ops


def _filter_dh_moduli() -> OperationMeta | None:
    """Drop sub-3072-bit DH group-exchange moduli (sshd picks from this file at negotiation time)."""

    weak = (
        host.get_fact(
            Command,
            f"awk '$5+0 > 0 && $5+0 < {MIN_DH_MODULUS_SIZE} {{print; exit}}' {SSH_MODULI_PATH} 2>/dev/null || true",
            _sudo=True,
        )
        or ""
    )
    if not str(weak).strip():
        return None

    return server.shell(
        name="Drop weak DH group-exchange moduli",
        commands=[
            f"awk '/^#/ || $5+0 >= {MIN_DH_MODULUS_SIZE}' {SSH_MODULI_PATH} > {SSH_MODULI_PATH}.tmp"
            f" && test -s {SSH_MODULI_PATH}.tmp"
            f" && mv {SSH_MODULI_PATH}.tmp {SSH_MODULI_PATH}",
        ],
        _sudo=True,
    )


def _enhance_ssh_daemon(user_opts: UserMold, ssh_opts: SshMold) -> None:
    """Enhance SSH daemon configuration."""

    pm = get_pm()

    sshd_directives = [
        ("Modify SSH password authentication", "PasswordAuthentication", "no", user_opts.manage),
        ("Disable SSH root login", "PermitRootLogin", "no", True),
        ("Enable DNS resolution for SSH", "UseDNS", "yes", True),
    ]

    config_ops: list[OperationMeta] = []
    for op_name, directive, value, should_apply in host.loop(sshd_directives):
        if not should_apply:
            continue
        config_ops.append(
            files.line(
                name=op_name,
                path=SSHD_CONFIG_PATH,
                line=rf"^[[:space:]]*#?[[:space:]]*{directive}[[:space:]]+.*",
                replace=f"{directive} {value}",
                extended_regex=True,
                _sudo=True,
            )
        )

    config_ops.extend(_configure_sshd_dropin(ssh_opts))

    if ssh_opts.strip_weak_algorithms:
        moduli_op = _filter_dh_moduli()
        if moduli_op:
            config_ops.append(moduli_op)

    if config_ops:
        server.shell(
            name="Validate sshd configuration",
            commands=["/usr/sbin/sshd -t"],
            _sudo=True,
            _if=any_changed(*config_ops),
        )

        service_name = "ssh" if pm.is_debian_based else "sshd"
        systemd.service(
            name="Restart SSH on change",
            service=service_name,
            restarted=True,
            _sudo=True,
            _if=any_changed(*config_ops),
        )

        systemd.service(
            name="Ensure SSH is running and enabled",
            service=service_name,
            running=True,
            enabled=True,
            _sudo=True,
        )


def _resolve_conntrack_sysctls(configured: dict[str, int] | None) -> dict[str, int] | None:
    if not configured:
        return configured

    if not module_loaded("nf_conntrack"):
        return None

    ct_max_target = conntrack_max_for(get_total_memory())
    ct_buckets = max(4096, (ct_max_target + 3) // 4)
    runtime_sizing = {
        "net.netfilter.nf_conntrack_max": ct_buckets * 4,
    }
    return {**runtime_sizing, **configured}


def _apply_sysctl_tuning(opts: NetSecMold) -> None:
    """Apply system kernel parameter tuning."""

    persist_map = [
        ("system", opts.system_sysctl, "/etc/sysctl.d/99-system.conf"),
        ("conntrack", _resolve_conntrack_sysctls(opts.conntrack_sysctl), "/etc/sysctl.d/99-conntrack.conf"),
        ("ipv4", opts.ipv4_sysctl, "/etc/sysctl.d/99-ipv4.conf"),
        ("ipv6", opts.ipv6_sysctl if has_ipv6() else None, "/etc/sysctl.d/99-ipv6.conf"),
    ]

    for desc, sysctls, persist_file in host.loop(persist_map):
        if not sysctls:
            continue

        for key, value in host.loop(sysctls.items()):
            server.sysctl(
                name=f"Set sysctl {key} ({desc})",
                key=key,
                value=str(value),
                persist=True,
                persist_file=persist_file,
                _sudo=True,
            )


deploy_network_security()
