"""DNS configuration deployment module."""

from pyinfra.context import host
from pyinfra.facts.files import Link
from pyinfra.operations import files, server, systemd
from pyinfra.operations.util import any_changed

from nullforge.models.dns import (
    DnsMode,
    DnsProtocol,
    DnsServer,
    DnsServerDoH,
    DnsServerDoT,
    DnsServerDoU,
    dns_providers,
)
from nullforge.molds import DnsMold, FeaturesMold
from nullforge.smithy.blocky import BLOCKY_GROUP, BLOCKY_USER, ensure_blocky_binary
from nullforge.smithy.network import has_ipv6
from nullforge.smithy.service import ensure_service_user
from nullforge.templates import BLOCK_TRIM_ENV, get_template_path


def deploy_dns_configuration() -> None:
    """Deploy DNS configuration based on selected mode."""

    ipv6_enabled = has_ipv6()
    features: FeaturesMold = host.data.features
    dns_opts: DnsMold = features.dns

    upstream_protocol = (
        DnsProtocol.DOH
        if dns_opts.mode == DnsMode.BLOCKY
        else DnsProtocol.DOT
        if dns_opts.mode == DnsMode.DOT_RESOLVED
        else None
    )

    upstreams: list[DnsServer] = (
        dns_providers.get_upstreams(
            dns_opts.upstream_provider,
            upstream_protocol,
            ipv6_enabled,
            dns_opts.ecs,
        )
        if upstream_protocol
        else []
    )

    match dns_opts.mode:
        case DnsMode.DOU:
            raise ValueError("DNS over UDP is not supported yet.")
        case DnsMode.DOT_RESOLVED:
            _deploy_dot_resolved(dns_opts, upstreams)
        case DnsMode.BLOCKY:
            _deploy_blocky_configuration(dns_opts, upstreams)
        case DnsMode.NONE:
            return
        case _:
            raise NotImplementedError(f"Unsupported DNS mode: {dns_opts.mode}")


def _format_resolved_upstreams(upstreams: list[DnsServer]) -> list[str]:
    """Render DoT upstreams in `address[:port]#SNI` form for systemd-resolved."""

    servers: list[str] = []
    for srv in [u for u in upstreams if isinstance(u, DnsServerDoT)]:
        addr = str(srv.host)
        endpoint = f"[{addr}]:{srv.port}" if ":" in addr else f"{addr}:{srv.port}"
        servers.append(f"{endpoint}#{srv.sni}" if srv.sni else endpoint)
    return servers


def _deploy_dot_resolved(opts: DnsMold, upstreams: list[DnsServer]) -> None:
    """Deploy DNS over TLS configuration."""

    systemd.service(
        name="Stop and disable blocky DNS proxy",
        service="blocky",
        running=False,
        enabled=False,
        _sudo=True,
        _ignore_errors=True,
    )

    systemd.service(
        name="Stop and disable dns-internal interface",
        service="dns-internal",
        running=False,
        enabled=False,
        _sudo=True,
        _ignore_errors=True,
    )

    resolved_conf = files.template(
        name="Configure systemd-resolved for DoT",
        src=get_template_path("dns/resolved.conf.j2"),
        dest="/etc/systemd/resolved.conf",
        mode="0644",
        DOT=True,
        DOH=False,
        DNS_SERVERS=_format_resolved_upstreams(upstreams),
        _sudo=True,
    )

    stub_resolv_conf = "/run/systemd/resolve/stub-resolv.conf"
    resolv_conf = "/etc/resolv.conf"
    resolved_link = files.link(
        name="Create symlink to resolv.conf for DoT with systemd-resolved",
        path=resolv_conf,
        target=stub_resolv_conf,
        force=True,
        _sudo=True,
    )

    systemd.service(
        name="Restart systemd-resolved on change",
        service="systemd-resolved",
        restarted=True,
        _sudo=True,
        _if=any_changed(resolved_conf, resolved_link),
    )

    systemd.service(
        name="Ensure systemd-resolved is running and enabled",
        service="systemd-resolved",
        running=True,
        enabled=True,
        _sudo=True,
    )

    server.shell(
        name="Flush DNS cache",
        commands=[
            "resolvectl flush-caches",
        ],
        _sudo=True,
        _if=any_changed(resolved_conf, resolved_link),
    )


def _format_blocky_upstreams(upstreams: list[DnsServer]) -> list[str]:
    result = []
    for srv in upstreams:
        if isinstance(srv, DnsServerDoH):
            result.append(srv.url)
        elif isinstance(srv, DnsServerDoT):
            addr = f"[{srv.host}]" if ":" in str(srv.host) else str(srv.host)
            result.append(f"tcp-tls:{addr}:{srv.port}")
        elif isinstance(srv, DnsServerDoU):
            addr = f"[{srv.host}]" if ":" in str(srv.host) else str(srv.host)
            result.append(f"udp://{addr}:{srv.port}")
    return result


def _deploy_blocky_configuration(opts: DnsMold, upstreams: list[DnsServer]) -> None:
    """Deploy blocky DNS proxy on the internal link-local interface."""

    ensure_service_user(BLOCKY_USER, BLOCKY_GROUP, "/etc/blocky")
    binary_op = ensure_blocky_binary()
    listen = opts.listen_address

    if opts.needs_custom_interface:
        iface_service_path = "/etc/systemd/system/dns-internal.service"
        iface_service = files.template(
            name="Configure dns-internal dummy interface service",
            src=get_template_path("systemd/dns-internal.service.j2"),
            dest=iface_service_path,
            mode="0644",
            LISTEN_ADDRESS=listen,
            LISTEN_CIDR=f"{listen}/{listen.max_prefixlen}",
            _sudo=True,
        )

        systemd.daemon_reload(
            name="Reload systemd daemon for dns-internal",
            _sudo=True,
            _if=iface_service.did_change,
        )

        systemd.service(
            name="Ensure dns-internal interface is running and enabled",
            service="dns-internal",
            running=True,
            enabled=True,
            _sudo=True,
        )

    # Deploy blocky config
    config_dir = "/etc/blocky"
    config_path = f"{config_dir}/config.yaml"
    config_template = files.template(
        name="Configure blocky DNS YAML config",
        src=get_template_path("dns/blocky.yaml.j2"),
        dest=config_path,
        mode="0644",
        user=BLOCKY_USER,
        group=BLOCKY_GROUP,
        jinja_env_kwargs=BLOCK_TRIM_ENV,
        UPSTREAMS=_format_blocky_upstreams(upstreams),
        LISTEN_ENDPOINT=f"[{listen}]:53" if listen.version == 6 else f"{listen}:53",
        _sudo=True,
    )

    service_path = "/etc/systemd/system/blocky.service"
    service_template = files.template(
        name="Configure blocky DNS proxy service",
        src=get_template_path("systemd/blocky.service.j2"),
        dest=service_path,
        mode="0644",
        CONFIG_PATH=config_path,
        _sudo=True,
    )

    systemd.daemon_reload(
        name="Reload systemd daemon for blocky",
        _sudo=True,
        _if=service_template.did_change,
    )

    restart_ops = [op for op in (binary_op, config_template, service_template) if op]
    systemd.service(
        name="Restart blocky on change",
        service="blocky",
        restarted=True,
        _sudo=True,
        _if=any_changed(*restart_ops),
    )

    systemd.service(
        name="Ensure blocky is running and enabled",
        service="blocky",
        running=True,
        enabled=True,
        _sudo=True,
    )

    if host.get_fact(Link, path="/etc/resolv.conf"):
        files.link(
            name="Remove /etc/resolv.conf symlink",
            path="/etc/resolv.conf",
            present=False,
            _sudo=True,
        )

    files.template(
        name="Configure resolv.conf for blocky",
        src=get_template_path("dns/resolv.conf.j2"),
        dest="/etc/resolv.conf",
        mode="0644",
        LISTEN_ADDRESS=opts.listen_address,
        _sudo=True,
    )


deploy_dns_configuration()
