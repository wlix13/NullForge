"""Cloudflare WARP deployment module."""

from pyinfra.api.operation import OperationMeta
from pyinfra.context import host
from pyinfra.facts.files import File
from pyinfra.operations import files, server, systemd
from pyinfra.operations.util import any_changed

from nullforge.models.warp import WarpEngineType
from nullforge.molds import FeaturesMold, WarpMold
from nullforge.smithy.cloudflare import CLOUDFLARE_GROUP, CLOUDFLARE_USER
from nullforge.smithy.install import install_release_binary
from nullforge.smithy.network import has_ipv6
from nullforge.smithy.packages import get_pm
from nullforge.smithy.service import ensure_service_user
from nullforge.smithy.versions import get_versions, is_pinned_version_installed, record_installed_version
from nullforge.templates import get_template_path


def deploy_warp() -> None:
    """Deploy Cloudflare WARP configuration."""

    features: FeaturesMold = host.data.features
    warp_opts: WarpMold = features.warp

    ensure_service_user(CLOUDFLARE_USER, CLOUDFLARE_GROUP, "/etc/cloudflare")

    files.directory(
        name="Ensure WARP engine configuration directory exists",
        path=warp_opts.engine.config_dir,
        user=CLOUDFLARE_USER,
        group=CLOUDFLARE_GROUP,
        mode="0755",
        _sudo=True,
    )

    match warp_opts.engine_type:
        case WarpEngineType.WIREGUARD:
            _deploy_wireguard_warp(warp_opts)
        case WarpEngineType.MASQUE:
            _deploy_masque_warp(warp_opts)


def _install_wgcf(opts: WarpMold) -> None:
    """Install wgcf binary."""

    if is_pinned_version_installed("wgcf", opts.engine.binary_path):
        return

    install_release_binary(
        name="Install wgcf binary",
        url=get_versions().wgcf_url(),
        dest=opts.engine.binary_path,
    )

    record_installed_version("wgcf")


def _deploy_wireguard_warp(opts: WarpMold) -> None:
    """Deploy WARP using WireGuard."""

    pm = get_pm()
    pm.install(
        name="Install WireGuard packages",
        packages=["wireguard", "wireguard-tools"],
        _sudo=True,
    )

    _install_wgcf(opts)

    wgcf_account_path = opts.engine.account_path
    wgcf_profile_path = opts.engine.profile_path
    wgcf_bin = opts.engine.binary_path

    register_op = None
    if not host.get_fact(File, wgcf_account_path):
        register_op = server.shell(
            name="Register wgcf account",
            commands=f"{wgcf_bin} register --accept-tos --config {wgcf_account_path}",
            _retries=3,
            _retry_delay=10,
            _ignore_errors=True,
        )

    register_condition = register_op.did_succeed if register_op else (lambda: True)

    generate_op = None
    if not host.get_fact(File, wgcf_profile_path):
        generate_op = server.shell(
            name="Generate WireGuard profile",
            commands=f"{wgcf_bin} generate --config {wgcf_account_path} --profile {wgcf_profile_path}",
            _retries=3,
            _retry_delay=10,
            _ignore_errors=True,
            _if=register_condition,
        )

        server.shell(
            name="Post-process WireGuard profile",
            commands=f"sed -i '/^DNS = /d' {wgcf_profile_path} "
            rf"&& sed -i '/^\[Interface\]/a Table = off' {wgcf_profile_path}",
            _if=generate_op.did_change,
        )

    def _wgcf_ok() -> bool:
        """True iff every declared wgcf step really succeeded (or none were declared)."""

        if register_op is not None and not register_op.did_succeed():
            return False
        if generate_op is not None and not generate_op.did_succeed():
            return False
        return True

    profile_link = files.link(
        name="Link WireGuard profile to /etc/wireguard/warp.conf",
        path="/etc/wireguard/warp.conf",
        target=wgcf_profile_path,
        _sudo=True,
        _if=_wgcf_ok,
    )

    restart_ops = [op for op in (register_op, generate_op, profile_link) if op]
    systemd.service(
        name="Restart WireGuard WARP on change",
        service=opts.engine.systemd_service_name,
        restarted=True,
        _sudo=True,
        _if=[_wgcf_ok, any_changed(*restart_ops)],
    )

    systemd.service(
        name="Ensure WireGuard WARP is running and enabled",
        service=opts.engine.systemd_service_name,
        running=True,
        enabled=True,
        _sudo=True,
        _if=_wgcf_ok,
    )


def _install_usque(opts: WarpMold) -> OperationMeta | None:
    """Install usque binary."""

    if is_pinned_version_installed("usque", opts.engine.binary_path):
        return None

    install_op = install_release_binary(
        name="Extract and install usque binary",
        url=get_versions().usque_zip(),
        dest=opts.engine.binary_path,
        binary_name="usque",
    )

    files.file(
        name="Set usque binary as executable",
        path=opts.engine.binary_path,
        mode="0755",
        user="root",
        group=CLOUDFLARE_GROUP,
        _sudo=True,
    )

    return install_op


def _deploy_masque_warp(opts: WarpMold) -> None:
    """Deploy WARP using Masque."""

    binary_op = _install_usque(opts)

    usque_config_path = opts.engine.config_path
    usque_bin = opts.engine.binary_path
    if not host.get_fact(File, usque_config_path):
        server.shell(
            name="Enroll device in Warp",
            commands=f"{usque_bin} enroll -c {usque_config_path}",
            _sudo=True,
        )

        register_op = server.shell(
            name="Register device in Warp",
            commands=f"{usque_bin} register -c {usque_config_path} --accept-tos",
            _sudo=True,
            _retries=3,
            _retry_delay=10,
            _ignore_errors=True,
        )
        config_condition = register_op.did_succeed
    else:
        config_condition = lambda: True  # noqa: E731  # config already exists, ops run unconditionally

    files.file(
        name="Ensure WARP config file ownership to cloudflare",
        path=usque_config_path,
        user=CLOUDFLARE_USER,
        group=CLOUDFLARE_GROUP,
        mode="0640",
        _sudo=True,
        _if=config_condition,
    )

    rt_tables_dir = "/etc/iproute2"
    rt_tables_path = f"{rt_tables_dir}/rt_tables"
    files.directory(
        name="Create /etc/iproute2 directory",
        path=rt_tables_dir,
        user="root",
        group="root",
        mode="0755",
        _sudo=True,
        _if=config_condition,
    )

    files.file(
        name=f"Set {rt_tables_path} group to cloudflare",
        path=rt_tables_path,
        group=CLOUDFLARE_GROUP,
        mode="0664",
        _sudo=True,
        _if=config_condition,
    )

    policy_script = files.put(
        name="Deploy WARP v6 policy script",
        src=get_template_path("scripts/warp-v6-policy.sh"),
        dest=opts.engine.policy_script,
        user=CLOUDFLARE_USER,
        group=CLOUDFLARE_GROUP,
        mode="0755",
        _sudo=True,
        _if=config_condition,
    )

    service_template = files.template(
        name="Deploy Masque WARP service configuration",
        src=get_template_path("systemd/cloudflare-warp.service.j2"),
        dest=f"/etc/systemd/system/{opts.engine.systemd_service_name}.service",
        mode="0644",
        WORKDIR=opts.engine.config_dir,
        CONFIG_PATH=opts.engine.config_path,
        MTU=opts.mtu,
        INET_NAME=opts.iface,
        USE_OUTBOUND_IPV6=has_ipv6(exclude_iface=opts.iface),
        _sudo=True,
        _if=config_condition,
    )

    systemd.daemon_reload(
        name="Reload systemd daemon for Masque WARP",
        _sudo=True,
        _if=any_changed(policy_script, service_template),
    )

    restart_ops = [op for op in (binary_op, policy_script, service_template) if op]
    systemd.service(
        name="Restart Masque WARP on change",
        service=opts.engine.systemd_service_name,
        restarted=True,
        _sudo=True,
        _if=any_changed(*restart_ops),
    )

    systemd.service(
        name="Ensure Masque WARP is running and enabled",
        service=opts.engine.systemd_service_name,
        running=True,
        enabled=True,
        _sudo=True,
        _if=config_condition,
    )


deploy_warp()
