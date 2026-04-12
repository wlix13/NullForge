"""Base system configuration deployment module."""

import re

from pyinfra.context import host
from pyinfra.facts.files import File, FileContents
from pyinfra.facts.server import Command, Hostname, Locales
from pyinfra.operations import files, server, systemd

from nullforge.molds import SystemMold
from nullforge.smithy.install import install_release_binary
from nullforge.smithy.packages import get_pm
from nullforge.smithy.swap import configure_swap
from nullforge.smithy.system import detect_best_locale
from nullforge.smithy.versions import get_versions, is_pinned_version_installed


def deploy_base_system() -> None:
    """Deploy base system configuration."""

    system: SystemMold = host.data.system

    if system.ensure_ipv6:
        _ensure_ipv6_stack()

    if system.hostname:
        _configure_hostname(system.hostname)

    _install_packages(system)

    _set_locale(system)

    _set_timezone(system)

    _configure_ntp()

    configure_swap(system)


def _configure_hostname(hostname: str) -> None:
    """Configure system hostname."""

    short_hostname = hostname.split(".")[0]

    ip_fact = host.get_fact(Command, "hostname -I | awk '{print $1}'") or ""
    ip = ip_fact.strip() or "127.0.1.1"

    if host.get_fact(Hostname) != hostname:
        server.hostname(
            name="Set system hostname",
            hostname=hostname,
            _sudo=True,
        )

    server.etc_hosts(
        name="Ensure hostname in hosts file",
        ip=ip,
        hostnames=[hostname, short_hostname],
        _sudo=True,
    )

    _disable_cloud_init_hostname()


def _disable_cloud_init_hostname() -> None:
    """Prevent cloud-init from overriding the configured hostname on reboot."""

    cloud_cfg = "/etc/cloud/cloud.cfg"
    if not host.get_fact(File, cloud_cfg):
        return

    files.line(
        name="Preserve hostname across cloud-init runs",
        path=cloud_cfg,
        line=r"^preserve_hostname:.*",
        replace="preserve_hostname: true",
        _sudo=True,
    )

    for module in host.loop(("set_hostname", "update_hostname")):
        files.line(
            name=f"Remove {module} from cloud_init_modules",
            path=cloud_cfg,
            line=rf"^\s*-\s+{module}\s*$",
            present=False,
            _sudo=True,
        )


def _install_packages(system: SystemMold) -> None:
    """Install base system packages."""

    pm = get_pm()

    pm.update(
        name="Update package repositories",
        _sudo=True,
    )

    pm.upgrade(
        name="Update packages",
        _sudo=True,
    )

    pm.install(
        name="Install base system packages",
        packages=system.packages_base,
        no_recommends=True,
        _sudo=True,
    )

    _install_curl()

    _install_doggo()


def _install_curl() -> None:
    """Install curl package."""

    pm = get_pm()
    curl_exec_path = "/usr/local/bin/curl"
    if is_pinned_version_installed("curl", curl_exec_path):
        return

    try:
        curl_url = get_versions().curl_tar()
    except ValueError:
        pm.install(
            name="Install curl package from repo",
            packages=["curl"],
            _sudo=True,
        )
        return

    install_release_binary(
        name="Install curl binary from static-curl",
        url=curl_url,
        dest=curl_exec_path,
        binary_name="curl",
    )

    if not pm.is_debian_based:
        files.link(
            name="Symlink Debian-style CA bundle path for static curl",
            path="/etc/ssl/certs/ca-certificates.crt",
            target="/etc/pki/tls/certs/ca-bundle.crt",
            _sudo=True,
        )
        return

    pm.install(
        name="Remove curl package",
        packages=["curl"],
        present=False,
        _sudo=True,
    )

    pm.upgrade(
        name="Clean up unused packages",
        auto_remove=True,
        _sudo=True,
    )


def _install_doggo() -> None:
    """Install doggo package."""

    if is_pinned_version_installed("doggo", "/usr/local/bin/doggo"):
        return

    install_release_binary(
        name="Download and extract doggo",
        url=get_versions().doggo_tar(),
        dest="/usr/local/bin/doggo",
        binary_name="doggo",
    )


def _set_locale(system: SystemMold) -> None:
    """Set system locale."""

    resolved_locales = set[str]()

    for locale in system.locales:
        best = detect_best_locale(preferred=locale)
        if best:
            resolved_locales.add(best)

    if not resolved_locales:
        return

    installed = host.get_fact(Locales)
    needs_gen = False

    for gen_line in host.loop(sorted(resolved_locales)):
        name = gen_line.split()[0]
        files.line(
            name=f"Enable locale {name}",
            path="/etc/locale.gen",
            line=rf"^#?\s*{re.escape(gen_line)}$",
            replace=gen_line,
            _sudo=True,
        )
        if name not in installed:
            needs_gen = True

    if needs_gen:
        server.shell(
            name="Generate locales",
            commands=["locale-gen"],
            _sudo=True,
        )


def _configure_ntp() -> None:
    """Install and configure NTP synchronization."""

    pm = get_pm()

    if pm.is_debian_based:
        pm.install(
            name="Install systemd-timesyncd",
            packages=["systemd-timesyncd"],
            _sudo=True,
        )
        systemd.service(
            name="Ensure systemd-timesyncd is running and enabled",
            service="systemd-timesyncd",
            running=True,
            enabled=True,
            _sudo=True,
        )
    elif pm.is_rhel_based:
        pm.install(
            name="Install chrony",
            packages=["chrony"],
            _sudo=True,
        )
        systemd.service(
            name="Ensure chronyd is running and enabled",
            service="chronyd",
            running=True,
            enabled=True,
            _sudo=True,
        )
        server.shell(
            name="Force NTP sync",
            commands=["chronyc makestep"],
            _sudo=True,
            _retries=3,
            _retry_delay=5,
        )
    else:
        raise NotImplementedError(f"NTP configuration is not supported for distro: {pm.distro_name}")


def _set_timezone(system: SystemMold) -> None:
    """Set system timezone."""

    server.timezone(
        name=f"Set system timezone to {system.timezone}",
        timezone=system.timezone,
        _sudo=True,
    )


def _ensure_ipv6_stack() -> None:
    """Ensure the kernel IPv6 stack is not disabled at boot."""

    grub_path = "/etc/default/grub"
    grub_contents = host.get_fact(FileContents, path=grub_path)

    if not grub_contents or not any("ipv6.disable=" in line for line in grub_contents):
        return

    remove_op = files.replace(
        name="Remove ipv6.disable=... from GRUB kernel command lines",
        path=grub_path,
        text=r"""(^|[ "])ipv6\.disable=[^"']*""",
        replace=r"\1",
        extended_regex=True,
        flags=["g"],
        _sudo=True,
    )

    collapse_op = files.replace(
        name="Collapse repeated spaces in GRUB_CMDLINE_LINUX* values",
        path=grub_path,
        text=r'(GRUB_CMDLINE_LINUX(_DEFAULT)?="[^"]*?) {2,}([^"]*?")',
        replace=r"\1 \2",
        extended_regex=True,
        flags=["g"],
        _sudo=True,
    )

    if remove_op.will_change or collapse_op.will_change:
        _update_grub_config()


def _update_grub_config() -> None:
    pm = get_pm()
    if pm.is_debian_based:
        server.shell(
            name="Regenerate GRUB config (update-grub)",
            commands=["update-grub"],
            _sudo=True,
        )
    elif pm.is_rhel_based:
        # try most common locations; failures for non-applicable paths are ignored.
        server.shell(
            name="Regenerate GRUB config (grub2-mkconfig)",
            commands=[
                (
                    "grub2-mkconfig -o /boot/grub2/grub.cfg 2>/dev/null || "
                    "grub2-mkconfig -o /boot/efi/EFI/redhat/grub.cfg 2>/dev/null || "
                    "grub2-mkconfig -o /boot/efi/EFI/centos/grub.cfg 2>/dev/null || "
                    "grub2-mkconfig -o /boot/efi/EFI/fedora/grub.cfg 2>/dev/null || "
                    "grub2-mkconfig -o /boot/efi/EFI/rocky/grub.cfg 2>/dev/null || "
                    "grub2-mkconfig -o /boot/efi/EFI/alma/grub.cfg 2>/dev/null || "
                    "true"
                )
            ],
            _sudo=True,
        )


deploy_base_system()
