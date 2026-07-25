"""HAProxy deployment module."""

from pyinfra import logger
from pyinfra.context import host
from pyinfra.facts.files import Directory
from pyinfra.operations import apt, files

from nullforge.molds import FeaturesMold, HaproxyMold
from nullforge.smithy.admin import ensure_acl_access
from nullforge.smithy.packages import get_pm
from nullforge.smithy.versions import GPG_KEYS, KEYRING_DIR


def deploy_haproxy() -> None:
    """Deploy HAProxy proxy server."""

    features: FeaturesMold = host.data.features
    haproxy_opts: HaproxyMold = features.haproxy

    _install_haproxy(haproxy_opts)
    _ensure_pki_dir()
    if features.users.manage:
        _setup_acls(features.users.name)


def _install_haproxy(opts: HaproxyMold) -> None:
    """Install HAProxy proxy server."""

    haproxy_version = opts.version

    pm = get_pm()

    if pm.is_debian_based:
        if pm.is_ubuntu:
            pm.install(
                name="Install software-properties-common",
                packages=["software-properties-common"],
                no_recommends=True,
                _sudo=True,
            )

            apt.ppa(
                name="Add HAProxy PPA",
                src=f"ppa:vbernat/haproxy-{haproxy_version}",
                _sudo=True,
            )

            pm.update(
                name="Update package repositories after adding HAProxy PPA",
                _sudo=True,
            )

            pm.install(
                name="Install HAProxy",
                packages=[f"haproxy={haproxy_version}.*"],
                _sudo=True,
            )

        else:
            # Debian 13 = trixie, Debian 12 = bookworm
            if pm.distro_major == 13:
                repo_version = f"trixie-backports-{haproxy_version}"
            elif pm.distro_major == 12:
                repo_version = f"bookworm-backports-{haproxy_version}"
            else:
                raise ValueError("Unsupported distribution version")

            gpg_key_path = f"{KEYRING_DIR}/haproxy-archive-keyring.gpg"
            apt.key(
                name="Install HAProxy GPG key",
                src=GPG_KEYS["haproxy"],
                dest=gpg_key_path,
                _sudo=True,
                _retries=3,
                _retry_delay=10,
            )

            apt.sources_file(
                name="Write HAProxy repository source",
                filename="haproxy",
                uris="https://haproxy.debian.net",
                suites=repo_version,
                components="main",
                signed_by=gpg_key_path,
                _sudo=True,
            )

            pm.update(
                name="Update package repositories after adding HAProxy repository",
                _sudo=True,
            )

            pm.install(
                name="Install HAProxy",
                packages=[f"haproxy={haproxy_version}.*"],
                _sudo=True,
            )

    elif pm.is_rhel_based:
        logger.warning(
            f"HAProxy version pin '{haproxy_version}' is Debian/Ubuntu-only; "
            f"installing version shipped within {pm.distro_name}"
        )
        pm.install(
            name="Install HAProxy",
            packages=["haproxy"],
            _sudo=True,
        )


def _ensure_pki_dir() -> None:
    """Ensure the HAProxy PKI directory exists for ACME certificate management."""

    pki_dir = "/usr/local/etc/haproxy/pki"
    if not host.get_fact(Directory, pki_dir):
        files.directory(
            name="Create HAProxy PKI directory",
            path=pki_dir,
            user="root",
            group="root",
            mode="0755",
            _sudo=True,
        )


def _setup_acls(username: str) -> None:
    """Set up ACLs on HAProxy directories for ACME certificate management."""

    haproxy_dir = "/etc/haproxy"
    pki_dir = "/usr/local/etc/haproxy/pki"
    ensure_acl_access(username, haproxy_dir, [f"{haproxy_dir}/haproxy.cfg"])
    ensure_acl_access(username, pki_dir)


deploy_haproxy()
