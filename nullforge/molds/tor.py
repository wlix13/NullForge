"""Tor proxy configuration mold."""

from pydantic import Field

from .base_mold import BaseMold


class TorMold(BaseMold):
    install: bool = Field(
        default=False,
        description="Whether to install Tor proxy",
    )
    socks_port: int = Field(
        default=9050,
        ge=1,
        le=65535,
        description="The port to use for the Tor proxy",
    )
    dns_port: int = Field(
        default=5353,
        ge=1,
        le=65535,
        description="The port to use for the Tor proxy DNS",
    )

    @property
    def is_active(self) -> bool:
        return self.install
