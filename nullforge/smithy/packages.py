"""Package management utilities for NullForge."""

from typing import TYPE_CHECKING, Any, Protocol, cast

from pyinfra.context import host
from pyinfra.facts.server import LinuxDistribution
from pyinfra.operations import apt, dnf


if TYPE_CHECKING:
    from pyinfra.api.host import Host

UBUNTU_OVERRIDES = {
    "ifupdown2": "ifupdown",
}
"""Specific overrides for Ubuntu"""

RHEL_OVERRIDES = {
    "aha": None,
    "apt-transport-https": None,
    "bat": "bat",
    "bind9-host": "bind-utils",
    "build-essential": "@Development Tools",
    "dnsutils": "bind-utils",
    "g++": "gcc-c++",
    "gnupg": "gnupg2",
    "ifupdown2": None,
    "iputils-ping": "iputils",
    "libevent-dev": "libevent-devel",
    "libnss-resolve": "systemd-resolved",
    "libssl-dev": "openssl-devel",
    "locales": "glibc-langpack-en",
    "mtr-tiny": "mtr",
    "ncat": "nmap-ncat",
    "ncurses-dev": "ncurses-devel",
    "pkg-config": "pkgconfig",
    "python3-dev": "python3-devel",
    "software-properties-common": None,
    "ufw": "firewalld",
}
"""Package overrides for RHEL/CentOS/Fedora families
Key: Canonical name (Debian/Ubuntu style)
Value: RHEL equivalent (or None to skip)
"""


class SystemPackageModule(Protocol):
    """Protocol for pyinfra package manager modules (apt, dnf, etc)."""

    def packages(self, packages: list[str] | None = None, **kwargs: Any) -> Any: ...
    def update(self, **kwargs: Any) -> Any: ...


class AptModule(SystemPackageModule, Protocol):
    """Protocol for apt module which includes upgrade."""

    def upgrade(self, **kwargs: Any) -> Any: ...


class PackageManager:
    def __init__(self, host: "Host"):
        self.host = host
        self.distro_info = host.get_fact(LinuxDistribution)
        self.distro_name = (self.distro_info.get("name") or "").lower()
        self.distro_major = self.distro_info.get("major", 0) or 0

    @property
    def is_debian_based(self) -> bool:
        return any(x in self.distro_name for x in ["debian", "ubuntu"])

    @property
    def is_rhel_based(self) -> bool:
        return any(x in self.distro_name for x in ["centos", "redhat", "rhel", "fedora", "rocky", "alma"])

    @property
    def is_ubuntu(self) -> bool:
        return "ubuntu" in self.distro_name

    @property
    def is_debian(self) -> bool:
        return "debian" in self.distro_name

    def _get_module(self) -> SystemPackageModule:
        if self.is_debian_based:
            return cast(SystemPackageModule, apt)
        elif self.is_rhel_based:
            return cast(SystemPackageModule, dnf)
        else:
            raise NotImplementedError(f"Unsupported distribution: {self.distro_name}")

    def map_package(self, package: str) -> str | None:
        """Map a package name to the current distro's equivalent."""

        if self.is_ubuntu and package in UBUNTU_OVERRIDES:
            return UBUNTU_OVERRIDES[package]

        if self.is_debian_based:
            return package

        if self.is_rhel_based and package in RHEL_OVERRIDES:
            return RHEL_OVERRIDES[package]

        # TODO: Maybe make better fallback mechanism
        return package

    def map_packages(self, packages: list[str]) -> list[str]:
        """Map a list of packages."""

        mapped = set()
        for p in packages:
            m = self.map_package(p)
            if m:
                mapped.add(m)
        return list(mapped)

    def update(self, **kwargs: Any) -> Any:
        """Refresh the package repository cache.

        On Debian/Ubuntu: runs `apt update`.
        On RHEL/Fedora: no-op — dnf has no separate cache refresh step;
        `dnf upgrade` fetches fresh metadata automatically.
        """

        mod = self._get_module()
        if self.is_debian_based:
            return mod.update(**kwargs)
        return None

    def upgrade(self, **kwargs: Any) -> Any:
        """Upgrade all installed packages.

        On Debian/Ubuntu: runs `apt upgrade`.
        On RHEL/Fedora: runs `dnf upgrade`, which also refreshes metadata.
        """

        call_kwargs = kwargs.copy()
        mod = self._get_module()

        if not self.is_debian_based:
            call_kwargs.pop("auto_remove", None)

        if self.is_debian_based:
            return cast(AptModule, mod).upgrade(**call_kwargs)
        elif self.is_rhel_based:
            return mod.update(**call_kwargs)
        return None

    def install(self, packages: list[str], **kwargs: Any) -> Any:
        """Install packages."""

        mod = self._get_module()
        mapped_packages = self.map_packages(packages)
        if not mapped_packages:
            return None

        call_kwargs = kwargs.copy()

        # Remove apt-specific kwargs if not apt
        if not self.is_debian_based:
            call_kwargs.pop("no_recommends", None)
            call_kwargs.pop("force", None)
            call_kwargs.pop("cache_time", None)
            call_kwargs.pop("extra_uninstall_args", None)

        return mod.packages(packages=mapped_packages, **call_kwargs)


def get_pm() -> PackageManager:
    """Get or create the PackageManager for the current host."""

    if hasattr(host.data, "_nullforge_package_manager"):
        return getattr(host.data, "_nullforge_package_manager")

    pm = PackageManager(host)
    setattr(host.data, "_nullforge_package_manager", pm)
    return pm
