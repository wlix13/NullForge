"""Tor proxy deployment module."""

from pyinfra.context import host
from pyinfra.operations import files, systemd

from nullforge.molds import FeaturesMold, TorMold
from nullforge.smithy.packages import get_pm
from nullforge.templates import get_template_path


def deploy_tor() -> None:
    """Deploy Tor proxy configuration."""

    features: FeaturesMold = host.data.features
    tor_opts: TorMold = features.tor

    _install_tor(tor_opts)


def _install_tor(opts: TorMold) -> None:
    """Install Tor proxy."""

    pm = get_pm()
    pm.install(
        name="Install Tor package",
        packages=["tor"],
        _sudo=True,
    )

    config_template = files.template(
        name="Deploy Tor proxy configuration",
        src=get_template_path("tor/torrc.j2"),
        dest="/etc/tor/torrc",
        mode="0644",
        SOCKS_PORT=opts.socks_port,
        DNS_PORT=opts.dns_port,
        _sudo=True,
    )

    systemd.service(
        name="Restart Tor on change",
        service="tor",
        restarted=True,
        _sudo=True,
        _if=config_template.did_change,
    )

    systemd.service(
        name="Ensure Tor is running and enabled",
        service="tor",
        running=True,
        enabled=True,
        _sudo=True,
    )


deploy_tor()
