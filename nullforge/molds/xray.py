"""Xray-core configuration mold."""

from pydantic import Field

from .base_mold import BaseMold


class XrayCoreMold(BaseMold):
    install: bool = Field(
        default=False,
        description="Whether to install Xray core",
    )

    @property
    def is_active(self) -> bool:
        return self.install
