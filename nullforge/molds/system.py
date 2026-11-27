"""Base system config: locales, timezone, base packages."""

from pydantic import Field, field_validator

from nullforge.models.system import SwapAlgo, SwapType

from .base_mold import BaseMold


def _default_packages_base() -> list[str]:
    """Get the default base packages to install."""

    return [
        "acl",
        "aha",
        "apt-transport-https",
        "bat",
        "bind9-host",
        "bison",
        "btop",
        "build-essential",
        "dnsutils",
        "duf",
        "file",
        "fontconfig",
        "g++",
        "gcc",
        "git",
        "gnupg",
        "ifupdown2",
        "ipcalc",
        "iputils-ping",
        "jq",
        "libevent-dev",
        "locales",
        "mtr-tiny",
        "ncat",
        "ncurses-dev",
        "net-tools",
        "nmap",
        "pkg-config",
        "unzip",
        "wget",
        "whois",
        "xsel",
        "zsh",
    ]


def _default_locales() -> list[str]:
    """Get the default locales to generate."""

    return ["en_US.UTF-8 UTF-8"]


def _default_timezone() -> str:
    """Get the default timezone."""

    return "Etc/UTC"


class SwapMold(BaseMold):
    """System swap configuration."""

    enabled: bool = Field(
        default=False,
        description="Whether swap should be enabled.",
    )
    type: SwapType = Field(
        default=SwapType.ZRAM,
        description="Type of swap to use (basic file or zram).",
    )
    algo: SwapAlgo = Field(
        default=SwapAlgo.ZSTD,
        description="Algorithm of ZRAM compression to use.",
    )
    size: str = Field(
        default="60%",
        description="Swap size (e.g., '4G', '512M', '50%'). For zram, usually percentage of RAM.",
    )
    swappiness: int = Field(
        default=70,
        description="Kernel swappiness value (0-100).",
        ge=0,
        le=100,
    )


class SystemMold(BaseMold):
    """Full system configuration mold."""

    packages_base: list[str] = Field(
        default_factory=_default_packages_base,
        min_length=1,
        description="System-wide base packages to install",
    )
    locales: list[str] = Field(
        default_factory=_default_locales,
        min_length=1,
        description="Locales to generate",
    )
    timezone: str = Field(
        default_factory=_default_timezone,
        description="System timezone (e.g. 'UTC' or 'Europe/Amsterdam')",
    )
    hostname: str | None = Field(
        default=None,
        description="System hostname (FQDN). If None, hostname is not configured.",
    )
    swap: SwapMold = Field(
        default_factory=SwapMold,
        description="Swap configuration.",
    )
    ensure_ipv6: bool = Field(
        default=True,
        description="Ensure IPv6 kernel stack.",
    )

    @field_validator("hostname")
    @classmethod
    def _validate_hostname(cls, v: str | None) -> str | None:
        """Validate hostname format."""

        if v is None:
            return v
        if not v or len(v) > 253:
            raise ValueError("hostname must be between 1 and 253 characters")
        if "." not in v:
            raise ValueError("hostname should be a FQDN (contain a dot)")
        labels = v.split(".")
        for label in labels:
            if not label:
                raise ValueError("hostname contains empty label (consecutive dots or leading/trailing dot)")
            if len(label) > 63:
                raise ValueError(f"hostname label '{label}' exceeds 63 characters")
            if label.startswith("-") or label.endswith("-"):
                raise ValueError(f"hostname label '{label}' cannot start or end with a hyphen")
            if not all(c.isalnum() or c == "-" for c in label):
                raise ValueError(f"hostname label '{label}' contains invalid characters")
        return v
