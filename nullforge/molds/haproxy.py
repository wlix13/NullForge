"""HAProxy configuration mold."""

from pydantic import Field

from .base_mold import BaseMold


class HaproxyMold(BaseMold):
    install: bool = Field(
        default=False,
        description="Whether to install HAProxy proxy server",
    )
    version: str = Field(
        default="3.2",
        description=(
            "HAProxy version to install from `haproxy.debian.net` (Debian) or `vbernat PPA` (Ubuntu). "
            "Ignored on RHEL-based distros, which only offer version shipped by distro."
        ),
    )

    @property
    def is_active(self) -> bool:
        return self.install
