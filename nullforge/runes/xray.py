"""Xray proxy deployment module."""

from pyinfra.context import host
from pyinfra.facts.files import File
from pyinfra.operations import files, server, systemd

from nullforge.molds import FeaturesMold, XrayCoreMold
from nullforge.smithy.admin import ensure_acl_access
from nullforge.smithy.http import curl_args, curl_args_str
from nullforge.smithy.versions import STATIC_URLS


GEOIP_DAT_URL = "https://github.com/Loyalsoldier/v2ray-rules-dat/releases/latest/download/geoip.dat"
GEOSITE_DAT_URL = "https://github.com/Loyalsoldier/v2ray-rules-dat/releases/latest/download/geosite.dat"

GEO_DATS = {
    "geoip.dat": GEOIP_DAT_URL,
    "geosite.dat": GEOSITE_DAT_URL,
}

BASE_DIR = "/usr/local/share/xray"
CONFIG_DIR = "/usr/local/etc/xray"


def deploy_xray() -> None:
    """Deploy Xray proxy configuration."""

    features: FeaturesMold = host.data.features
    xray_opts: XrayCoreMold = features.xray

    _install_xray(xray_opts)
    _download_geo_data()

    systemd.service(
        name="Ensure Xray is running and enabled",
        service="xray",
        running=True,
        enabled=True,
        _sudo=True,
    )

    if features.users.manage:
        _setup_acls(features.users.name)


def _install_xray(opts: XrayCoreMold) -> None:
    """Install Xray using official installation script."""

    if host.get_fact(File, "/usr/local/bin/xray"):
        return

    server.shell(
        name="Install Xray proxy",
        commands=(
            f'script="$(curl -L {curl_args_str(STATIC_URLS["xray_install"])} {STATIC_URLS["xray_install"]})"'
            ' && bash -lc "$script" @ install --beta'
        ),
        _sudo=True,
    )


def _download_geo_data() -> None:
    """Download GeoIP and GeoSite data files."""

    for file, url in host.loop(GEO_DATS.items()):
        files.download(
            name=f"Download {file}",
            src=url,
            dest=f"{BASE_DIR}/{file}",
            extra_curl_args=curl_args(url),
            _sudo=True,
            _retries=3,
            _retry_delay=10,
        )


def _setup_acls(username: str) -> None:
    """Set up ACLs on Xray directories for config management."""

    ensure_acl_access(username, BASE_DIR)
    ensure_acl_access(username, CONFIG_DIR, [f"{CONFIG_DIR}/config.json"])


deploy_xray()
