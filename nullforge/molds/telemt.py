"""Telemt (MTProto proxy) configuration mold."""

import re
from typing import ClassVar, Literal

from pydantic import Field, field_validator, model_validator

from .base_mold import BaseMold


TelemtIpPreference = Literal[4, 6]
"""Address family telemt prefers when both are available (network.prefer)."""

_SECRET_RE = re.compile(r"^[0-9a-f]{32}$")
"""Telemt user secrets are 16 bytes rendered as 32 lowercase hex characters."""

_USERNAME_RE = re.compile(r"^[A-Za-z0-9_-]+$")
"""Usernames become TOML keys under [access.users]."""


class TelemtMold(BaseMold):
    """Telemt MTProto proxy for Telegram."""

    _sensitive_fields: ClassVar[tuple[str, ...]] = ("users",)

    install: bool = Field(
        default=False,
        description="Whether to install the telemt MTProto proxy",
    )
    port: int = Field(
        default=8443,
        ge=1,
        le=65535,
        description="TCP port telemt listens on",
    )
    tls_domain: str = Field(
        default="",
        description="Fake-TLS / SNI masking domain used in generated ee-links (censorship.tls_domain)",
    )
    users: dict[str, str] = Field(
        default_factory=dict,
        description="Access users mapping username -> 32 hex-char secret ([access.users])",
    )
    max_connections: int = Field(
        default=16384,
        ge=1,
        le=65535,
        description="Maximum concurrent client connections (server.max_connections)",
    )
    client_handshake: int = Field(
        default=30,
        gt=0,
        le=300,
        description="Seconds for client to finish handshake (timeouts.client_handshake)",
    )
    fast_mode: bool = Field(
        default=True,
        description="Enable telemt fast mode (general.fast_mode)",
    )
    use_middle_proxy: bool = Field(
        default=False,
        description="Route via Telegram middle proxies to enable ad tags (general.use_middle_proxy)",
    )
    mode_classic: bool = Field(
        default=False,
        description="Enable classic (unobfuscated) MTProto mode (general.modes.classic)",
    )
    mode_secure: bool = Field(
        default=False,
        description="Enable secure (dd-prefixed) MTProto mode (general.modes.secure)",
    )
    mode_tls: bool = Field(
        default=True,
        description="Enable Fake-TLS (ee-prefixed) MTProto mode (general.modes.tls)",
    )
    ipv6: bool = Field(
        default=True,
        description="Allow IPv6 upstream connections (network.ipv6)",
    )
    prefer: TelemtIpPreference = Field(
        default=6,
        description="Preferred address family when both are available (network.prefer)",
    )
    api_enabled: bool = Field(
        default=False,
        description="Expose the local management/metrics API (server.api.enabled)",
    )
    unknown_sni_action: str | None = Field(
        default=None,
        description="How to treat connections with an unexpected SNI (censorship.unknown_sni_action)",
    )
    pq_check: bool = Field(
        default=True,
        description=(
            "Probe tls_domain for X25519MLKEM768 (post-quantum) support at deploy time and warn when "
            "it is missing, since Telegram's iOS client tends to get blocked on such domains"
        ),
    )
    route_via_warp: bool = Field(
        default=False,
        description="Route Telegram-bound egress through WARP via per-uid policy routing",
    )
    synfix: bool = Field(
        default=False,
        description="Apply MEKO SYN rate-limiting fix",
    )

    @property
    def is_active(self) -> bool:
        return self.install

    @field_validator("tls_domain")
    @classmethod
    def _strip_domain(cls, v: str) -> str:
        return v.strip()

    @field_validator("users")
    @classmethod
    def _validate_users(cls, v: dict[str, str]) -> dict[str, str]:
        normalized: dict[str, str] = {}
        for name, secret in v.items():
            if not _USERNAME_RE.fullmatch(name):
                raise ValueError(f"Invalid telemt username {name!r}: use only letters, digits, '-' and '_'")
            secret = secret.strip().lower()
            if not _SECRET_RE.match(secret):
                raise ValueError(f"Invalid telemt secret for {name!r}: expected 32 hexadecimal characters")
            normalized[name] = secret
        return normalized

    @model_validator(mode="after")
    def _validate_enabled(self) -> "TelemtMold":
        if not self.install:
            return self
        if not self.users:
            raise ValueError("at least one entry in `users` is required when install is True")
        if self.mode_tls and not self.tls_domain:
            raise ValueError("`tls_domain` is required when install is True and the Fake-TLS mode is enabled")
        if not (self.mode_classic or self.mode_secure or self.mode_tls):
            raise ValueError("at least one of mode_classic/mode_secure/mode_tls must be enabled when install is True")
        return self
