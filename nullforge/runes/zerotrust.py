"""Cloudflare Zero Trust Tunnel deployment module."""

from pyinfra.context import host
from pyinfra.operations import files, systemd
from pyinfra.operations.util import any_changed

from nullforge.molds import FeaturesMold, WarpMold, ZeroTrustTunnelMold
from nullforge.smithy.cloudflare import CLOUDFLARE_GROUP, CLOUDFLARE_USER, ensure_cloudflared_binary
from nullforge.smithy.service import ensure_service_user
from nullforge.templates import BLOCK_TRIM_ENV, get_template_path


def deploy_zerotrust_tunnel() -> None:
    features: FeaturesMold = host.data.features
    tunnel_opts: ZeroTrustTunnelMold = features.zerotrust

    _deploy_tunnel(tunnel_opts, features.warp)


def _deploy_tunnel(opts: ZeroTrustTunnelMold, warp_opts: WarpMold) -> None:
    ensure_service_user(CLOUDFLARE_USER, CLOUDFLARE_GROUP, "/etc/cloudflare")
    binary_op = ensure_cloudflared_binary()

    config_dir = "/etc/cloudflare"
    config_path = f"{config_dir}/tunnel.yml"
    config_template = files.template(
        name="Deploy Zero Trust Tunnel configuration",
        src=get_template_path("cloudflared/tunnel.yml.j2"),
        dest=config_path,
        mode="0600",
        user=CLOUDFLARE_USER,
        group=CLOUDFLARE_GROUP,
        jinja_env_kwargs=BLOCK_TRIM_ENV,
        TOKEN=opts.token,
        PROTOCOL=opts.protocol,
        HA_CONNECTIONS=opts.ha_connections,
        POST_QUANTUM=opts.post_quantum,
        _sudo=True,
    )

    warp_route_script = None
    if opts.route_through_warp:
        warp_route_script = files.put(
            name="Deploy Zero Trust tunnel WARP routing script",
            src=get_template_path("scripts/zt-tunnel-warp.sh"),
            dest=f"{config_dir}/zt-tunnel-warp.sh",
            user=CLOUDFLARE_USER,
            group=CLOUDFLARE_GROUP,
            mode="0755",
            _sudo=True,
        )

    service_template = files.template(
        name="Deploy Zero Trust Tunnel systemd service",
        src=get_template_path("systemd/cloudflare-tunnel.service.j2"),
        dest="/etc/systemd/system/cloudflare-tunnel.service",
        mode="0644",
        jinja_env_kwargs=BLOCK_TRIM_ENV,
        CONFIG_PATH=config_path,
        WORKDIR=config_dir,
        ROUTE_THROUGH_WARP=opts.route_through_warp,
        WARP_IFACE=warp_opts.iface,
        WARP_SERVICE=warp_opts.engine.systemd_service_name,
        _sudo=True,
    )

    systemd.daemon_reload(
        name="Reload systemd daemon for Zero Trust Tunnel",
        _sudo=True,
        _if=service_template.did_change,
    )

    restart_ops = [op for op in (binary_op, config_template, service_template, warp_route_script) if op]
    systemd.service(
        name="Restart Zero Trust Tunnel on change",
        service="cloudflare-tunnel",
        restarted=True,
        _sudo=True,
        _if=any_changed(*restart_ops),
    )

    systemd.service(
        name="Ensure Zero Trust Tunnel is running and enabled",
        service="cloudflare-tunnel",
        running=True,
        enabled=True,
        _sudo=True,
    )


deploy_zerotrust_tunnel()
