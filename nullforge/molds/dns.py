"""DNS configuration mold."""

from ipaddress import IPv4Address, IPv6Address
from typing import TYPE_CHECKING

from pydantic import Field, IPvAnyAddress, field_validator

from nullforge.models.dns import DnsMode, DnsProvider

from .base_mold import BaseMold


class DnsMold(BaseMold):
    """Full DNS configuration mold."""

    mode: DnsMode = Field(
        default=DnsMode.BLOCKY,
        description="How DNS resolution should be performed",
    )
    upstream_provider: DnsProvider = Field(
        default=DnsProvider.CLOUDFLARE,
        description="Provider for upstream servers.",
    )
    ecs: bool = Field(
        default=False,
        description="Enable ECS (EDNS Client Subnet) for upstream provider.",
    )
    listen_address: IPvAnyAddress = Field(
        default="169.254.0.53",
        validate_default=True,
        description=(
            "IP address blocky binds to. Wildcards and loopback use existing interfaces; "
            "non-global addresses create dedicated dummy interface."
        ),
    )

    @property
    def is_active(self) -> bool:
        return self.mode != DnsMode.NONE

    if TYPE_CHECKING:
        # NOTE: This stub widens `listen_address`
        # Keep the list in sync with the fields above when they change.
        def __init__(
            self,
            *,
            mode: DnsMode = DnsMode.BLOCKY,
            upstream_provider: DnsProvider = DnsProvider.CLOUDFLARE,
            ecs: bool = False,
            listen_address: IPvAnyAddress | str = "169.254.0.53",
        ) -> None: ...

    @field_validator("listen_address")
    @classmethod
    def _validate_listen_address(cls, v: IPv4Address | IPv6Address) -> IPv4Address | IPv6Address:
        if v.is_unspecified or v.is_loopback:
            return v

        if not v.is_global:
            return v

        raise ValueError(f"listen_address {v!r} must be a wildcard, loopback, or non-global address.")

    @property
    def needs_custom_interface(self) -> bool:
        """True when blocky should bind to dedicated dummy interface."""

        if self.listen_address.is_unspecified or self.listen_address.is_loopback:
            return False
        return True
