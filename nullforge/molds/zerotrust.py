"""Zero Trust Tunnel configuration mold."""

from pydantic import Field, field_validator, model_validator

from nullforge.models.zerotrust import ZeroTrustTunnelProtocol

from .base_mold import BaseMold


class ZeroTrustTunnelMold(BaseMold):
    install: bool = Field(
        default=False,
        description="Whether to deploy Zero Trust Tunnel",
    )
    token: str | None = Field(
        default=None,
        description="Tunnel token for authentication",
    )
    protocol: ZeroTrustTunnelProtocol = Field(
        default=ZeroTrustTunnelProtocol.AUTO,
        description="Tunnel protocol",
    )
    post_quantum: bool = Field(
        default=False,
        description="Whether to use post-quantum protocol",
    )
    ha_connections: int = Field(
        default=2,
        ge=1,
        le=4,
        description="Number of high-availability connections",
    )
    route_through_warp: bool = Field(
        default=False,
        description="Whether to route tunnel traffic through WARP interface",
    )

    @property
    def is_active(self) -> bool:
        return self.install

    @field_validator("token")
    @classmethod
    def _strip_token(cls, v: str | None) -> str | None:
        return v.strip() if v is not None else None

    @model_validator(mode="after")
    def validate_install_requires_token(self) -> "ZeroTrustTunnelMold":
        if self.install and not self.token:
            raise ValueError("token is required when install is True")
        return self

    @model_validator(mode="after")
    def validate_post_quantum_requires_protocol(self) -> "ZeroTrustTunnelMold":
        if self.post_quantum and self.route_through_warp:
            raise ValueError("post-quantum protocol is not supported when routing through WARP")
        if self.post_quantum and self.protocol == ZeroTrustTunnelProtocol.HTTP2:
            raise ValueError("post-quantum key agreement requires QUIC protocol")
        return self
