"""WARP configuration mold."""

from functools import cached_property
from typing import TYPE_CHECKING, Literal

from pydantic import Field, field_validator

from nullforge.models.warp import WarpEngineType, warp_engine_factory

from .base_mold import BaseMold


if TYPE_CHECKING:
    from nullforge.models.warp import WarpEngine


class WarpMold(BaseMold):
    install: bool = Field(
        default=False,
        description="Whether to deploy WARP",
    )
    engine_type: WarpEngineType = Field(
        default=WarpEngineType.MASQUE,
        description="The WARP engine to use",
    )
    iface: str = Field(
        default="warp",
        description="The name of the network interface for WARP",
    )
    mtu: int = Field(
        default=1280,
        ge=1280,
        le=9216,
        description="The MTU for the WARP interface",
    )
    zero_trust: Literal[False] = Field(
        default=False,
        description="ZeroTrust enrollment — not yet implemented, always False",
    )

    @property
    def is_active(self) -> bool:
        return self.install

    @field_validator("iface")
    @classmethod
    def _validate_iface(cls, v: str) -> str:
        if not v or any(ch.isspace() for ch in v):
            raise ValueError("iface must be a non-empty string without spaces")
        return v

    @cached_property
    def engine(self) -> "WarpEngine":
        return warp_engine_factory(self.engine_type)
