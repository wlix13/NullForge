"""Telemt MTProto proxy deployment module."""

import shlex

import click
from pyinfra import logger
from pyinfra.api.operation import OperationMeta
from pyinfra.context import host
from pyinfra.operations import files, server, systemd
from pyinfra.operations.util import any_changed

from nullforge.molds import FeaturesMold, TelemtMold, WarpMold
from nullforge.smithy.arch import arch_id
from nullforge.smithy.github import sha256_for_download_url
from nullforge.smithy.install import STAGING_DIR, install_release_binary
from nullforge.smithy.packages import get_pm
from nullforge.smithy.service import ensure_service_user
from nullforge.smithy.sni import (
    GROUP_X25519,
    GROUP_X25519MLKEM768,
    KeyExchangeReport,
    group_name,
    inspect_group,
)
from nullforge.smithy.versions import Versions, get_versions, is_pinned_version_installed, record_installed_version
from nullforge.templates import BLOCK_TRIM_ENV, get_template_path


TELEMT_USER = "telemt"
TELEMT_GROUP = "telemt"
CONFIG_DIR = "/etc/telemt"
CONFIG_PATH = f"{CONFIG_DIR}/telemt.toml"
BINARY_PATH = "/usr/local/bin/telemt"
TELEPROXY_SCRIPT = "/usr/local/sbin/teleproxy-warp.sh"
SYNFIX_SCRIPT = "/usr/local/sbin/telemt-synfix.sh"
ZAPRET2_DIR = "/opt/telemt-synfix"
NFQWS2_BIN = f"{ZAPRET2_DIR}/bin/nfqws2"
ZAPRET2_ARCH_DIRS = {
    "x86_64": "linux-x86_64",
    "arm64": "linux-arm64",
}
ZAPRET2_LUA_DIR = f"{ZAPRET2_DIR}/lua"
ZAPRET2_MTPROTO_LUA = f"{ZAPRET2_LUA_DIR}/mtproto.lua"
SERVICE_NAME = "telemt"
SERVICE_UNIT = f"/etc/systemd/system/{SERVICE_NAME}.service"
LOG = logger


def deploy_telemt() -> None:
    """Deploy the telemt MTProto proxy."""

    features: FeaturesMold = host.data.features
    telemt_opts: TelemtMold = features.telemt
    warp_opts: WarpMold = features.warp

    warp_active = warp_opts.is_active and telemt_opts.route_via_warp

    _vet_tls_domain(telemt_opts)

    ensure_service_user(TELEMT_USER, TELEMT_GROUP, CONFIG_DIR)

    binary_op = _install_telemt()
    config_op = _deploy_config(telemt_opts, warp_active, warp_opts.iface)

    teleproxy_op = _deploy_teleproxy_script() if warp_active else None
    synfix_ops = _deploy_synfix_scripts(telemt_opts) if telemt_opts.synfix else []

    unit_op = _deploy_service_unit(
        telemt_opts,
        warp_active=warp_active,
        warp_service=warp_opts.engine.systemd_service_name,
        warp_iface=warp_opts.iface,
    )

    systemd.daemon_reload(
        name="Reload systemd daemon for telemt",
        _sudo=True,
        _if=unit_op.did_change,
    )

    # The helper scripts run from telemt's ExecStartPre/ExecStopPost, so a change
    # to either takes effect on the next telemt (re)start.
    restart_ops = [op for op in (binary_op, config_op, teleproxy_op, *synfix_ops, unit_op) if op]
    systemd.service(
        name="Restart telemt on change",
        service=SERVICE_NAME,
        restarted=True,
        _sudo=True,
        _if=any_changed(*restart_ops),
    )

    systemd.service(
        name="Ensure telemt is running and enabled",
        service=SERVICE_NAME,
        running=True,
        enabled=True,
        _sudo=True,
    )


def _vet_tls_domain(opts: TelemtMold) -> None:
    """Report whether the Fake-TLS masking domain looks likely to get the proxy blocked.

    Telegram's iOS client expects masking domain to negotiate X25519MLKEM768 hybrid
    post-quantum key exchange; domains that instead fall back to X25519 are observed
    to get proxies blocked on iOS.
    """

    if not (opts.pq_check and opts.mode_tls and opts.tls_domain):
        return

    domain = opts.tls_domain
    report = inspect_group(domain, GROUP_X25519MLKEM768)
    verdict = _tls_domain_verdict(domain, report)

    if report.conclusive and report.supported:
        LOG.info(click.style(verdict, fg="green"))
    else:
        LOG.warning(verdict)


def _tls_domain_verdict(domain: str, report: KeyExchangeReport) -> str:
    """Phrase a key-exchange report as advice about a Fake-TLS masking domain."""

    wanted = group_name(GROUP_X25519MLKEM768)
    advice = f"pick a masking domain that offers {wanted}"

    if not report.conclusive:
        return f"telemt tls_domain '{domain}' could not be vetted for {wanted} support: {report.error}"
    if report.supported:
        return f"telemt tls_domain '{domain}' negotiates {wanted}"
    if not report.supports_tls13:
        return (
            f"telemt tls_domain '{domain}' does not support TLS 1.3, so it cannot offer {wanted}: "
            f"Telegram's iOS client is likely to be blocked on this domain, {advice}"
        )
    if report.fallback == GROUP_X25519:
        return (
            f"telemt tls_domain '{domain}' does not support {wanted} and falls back to "
            f"{group_name(GROUP_X25519)}: Telegram's iOS client is likely to be blocked on this "
            f"domain, {advice}"
        )
    return (
        f"telemt tls_domain '{domain}' does not support {wanted} and negotiates "
        f"{group_name(report.fallback)}: iOS clients may be unreliable, prefer to {advice}"
    )


def _install_telemt() -> OperationMeta | None:
    """Install the pinned telemt binary from its glibc release tarball."""

    if is_pinned_version_installed("telemt", BINARY_PATH):
        host.noop("telemt binary is already at the pinned version")
        return None

    return install_release_binary(
        name="Extract and install telemt binary",
        url=get_versions().telemt_tar(),
        dest=BINARY_PATH,
        binary_name="telemt",
    )


def _deploy_config(opts: TelemtMold, warp_active: bool, warp_iface: str) -> OperationMeta:
    """Render the telemt.toml configuration."""

    return files.template(
        name="Deploy telemt configuration",
        src=get_template_path("telemt/telemt.toml.j2"),
        dest=CONFIG_PATH,
        user=TELEMT_USER,
        group=TELEMT_GROUP,
        mode="0640",
        jinja_env_kwargs=BLOCK_TRIM_ENV,
        FAST_MODE=opts.fast_mode,
        USE_MIDDLE_PROXY=opts.use_middle_proxy,
        MODE_CLASSIC=opts.mode_classic,
        MODE_SECURE=opts.mode_secure,
        MODE_TLS=opts.mode_tls,
        MAX_CONNECTIONS=opts.max_connections,
        CLIENT_HANDSHAKE=opts.client_handshake,
        PORT=opts.port,
        API_ENABLED=opts.api_enabled,
        IPV6=opts.ipv6,
        PREFER=opts.prefer,
        TLS_DOMAIN=opts.tls_domain,
        UNKNOWN_SNI_ACTION=opts.unknown_sni_action,
        USERS=opts.users,
        ROUTE_VIA_WARP=warp_active,
        WARP_IFACE=warp_iface,
        _sudo=True,
    )


def _deploy_teleproxy_script() -> OperationMeta:
    """Deploy the per-uid WARP policy-routing helper (invoked from telemt.service)."""

    return files.put(
        name="Deploy teleproxy WARP routing script",
        src=get_template_path("scripts/teleproxy-warp.sh"),
        dest=TELEPROXY_SCRIPT,
        user="root",
        group="root",
        mode="0755",
        _sudo=True,
    )


def _deploy_synfix_scripts(opts: TelemtMold) -> list[OperationMeta]:
    """Deploy the MEKO fix helper. v2/v3 use nftables as xt_u32 fallback, v4 uses it for nfqws2."""

    packages = ["iptables", "nftables"]
    get_pm().install(
        name="Install telemt fix dependencies",
        packages=packages,
        _sudo=True,
    )

    ops: list[OperationMeta] = [
        files.put(
            name="Deploy telemt SYN-fix script",
            src=get_template_path("scripts/telemt-synfix.sh"),
            dest=SYNFIX_SCRIPT,
            user="root",
            group="root",
            mode="0755",
            _sudo=True,
        )
    ]

    if opts.synfix == "v4":
        zapret2_op = _install_zapret2()
        if zapret2_op:
            ops.append(zapret2_op)
        ops.append(_deploy_zapret2_lua())

    return ops


def _install_zapret2() -> OperationMeta | None:
    """Extract nfqws2 and zapret lua libs from pinned zapret2 release tarball."""

    if is_pinned_version_installed("zapret2", NFQWS2_BIN):
        host.noop("zapret2 nfqws2 is already at the pinned version")
        return None

    arch = arch_id()
    arch_dir = ZAPRET2_ARCH_DIRS.get(arch)
    if arch_dir is None:
        raise ValueError(f"Unsupported architecture for zapret2: {arch}")

    versions = get_versions()
    version = versions.versions["zapret2"]
    url = versions.zapret2_tar()
    archive = f"{STAGING_DIR}/zapret2.tar.gz"
    workdir = f"{STAGING_DIR}/zapret2"
    binary_src = f"{workdir}/zapret2-{version}/binaries/{arch_dir}/nfqws2"

    files.directory(
        name="Ensure staging directory for zapret2",
        path=STAGING_DIR,
        mode="0700",
        _sudo=True,
    )
    files.download(
        name="Download zapret2 release",
        src=url,
        dest=archive,
        force=True,
        sha256sum=sha256_for_download_url(url),
        extra_curl_args=Versions.release_curl_args(url),
        _sudo=True,
        _retries=3,
        _retry_delay=10,
    )

    q = shlex.quote
    op = server.shell(
        name="Extract nfqws2 and zapret lua libs",
        commands=[
            f"rm -rf {q(workdir)} && mkdir -p {q(workdir)}",
            f"tar -xzf {q(archive)} -C {q(workdir)}",
            f"install -D -m 0755 {q(binary_src)} {q(NFQWS2_BIN)}",
            f"mkdir -p {q(ZAPRET2_LUA_DIR)}",
            f"find {q(workdir)} -type f -name 'zapret-*.lua*' -exec cp {{}} {q(ZAPRET2_LUA_DIR)}/ \\;",
            f"rm -rf {q(workdir)} {q(archive)}",
        ],
        _sudo=True,
    )

    record_installed_version("zapret2")
    return op


def _deploy_zapret2_lua() -> OperationMeta:
    """Deploy the nfqws2 desync script used by the v4 fix."""

    return files.put(
        name="Deploy zapret2 mtproto desync lua",
        src=get_template_path("scripts/telemt-zapret2-mtproto.lua"),
        dest=ZAPRET2_MTPROTO_LUA,
        user="root",
        group="root",
        mode="0644",
        create_remote_dir=True,
        _sudo=True,
    )


def _deploy_service_unit(
    opts: TelemtMold,
    *,
    warp_active: bool,
    warp_service: str,
    warp_iface: str,
) -> OperationMeta:
    """Render the telemt systemd unit."""

    return files.template(
        name="Deploy telemt systemd service",
        src=get_template_path("systemd/telemt.service.j2"),
        dest=SERVICE_UNIT,
        mode="0644",
        jinja_env_kwargs=BLOCK_TRIM_ENV,
        USER=TELEMT_USER,
        GROUP=TELEMT_GROUP,
        BINARY_PATH=BINARY_PATH,
        CONFIG_PATH=CONFIG_PATH,
        PORT=opts.port,
        WARP_ENABLED=warp_active,
        WARP_SERVICE=warp_service,
        WARP_IFACE=warp_iface,
        TELEPROXY_SCRIPT=TELEPROXY_SCRIPT,
        SYNFIX_ENABLED=opts.synfix is not None,
        SYNFIX_SCRIPT=SYNFIX_SCRIPT,
        SYNFIX_TYPE=opts.synfix or "v2",
        _sudo=True,
    )


deploy_telemt()
