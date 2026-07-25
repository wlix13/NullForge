"""WARP configuration models."""

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, Field


class WarpEngineType(StrEnum):
    WIREGUARD = "wireguard"
    MASQUE = "masque"


class _WarpEngineBase(BaseModel):
    """Base for a WARP engine."""

    type: WarpEngineType = Field(description="The type of WARP engine")
    binary_path: str = Field(description="The path to the WARP binary")
    config_dir: str = Field(description="The path to the WARP configuration directory")
    systemd_service_name: str = Field(description="The name of the systemd service")
    policy_script: str = Field(default="", description="The path to the WARP policy script")

    @property
    def config_path(self) -> str:
        return f"{self.config_dir}/config.json"

    @property
    def account_path(self) -> str:
        return f"{self.config_dir}/wgcf-account.toml"

    @property
    def profile_path(self) -> str:
        return f"{self.config_dir}/warp.conf"


class MasqueWarpEngine(_WarpEngineBase):
    type: Literal[WarpEngineType.MASQUE] = WarpEngineType.MASQUE
    binary_path: Literal["/usr/local/bin/usque"] = "/usr/local/bin/usque"
    config_dir: Literal["/etc/usque"] = "/etc/usque"
    systemd_service_name: Literal["cloudflare-warp"] = "cloudflare-warp"
    policy_script: Literal["/etc/usque/warp-v6-policy.sh"] = "/etc/usque/warp-v6-policy.sh"


class WireguardWarpEngine(_WarpEngineBase):
    type: Literal[WarpEngineType.WIREGUARD] = WarpEngineType.WIREGUARD
    binary_path: Literal["/usr/local/bin/wgcf"] = "/usr/local/bin/wgcf"
    config_dir: Literal["/etc/wgcf"] = "/etc/wgcf"
    systemd_service_name: Literal["wg-quick@warp"] = "wg-quick@warp"
    policy_script: Literal[""] = ""


WarpEngine = Annotated[
    MasqueWarpEngine | WireguardWarpEngine,
    Field(discriminator="type"),
]


def warp_engine_factory(type: WarpEngineType) -> WarpEngine:
    match type:
        case WarpEngineType.MASQUE:
            return MasqueWarpEngine()
        case WarpEngineType.WIREGUARD:
            return WireguardWarpEngine()
        case _:
            raise ValueError(f"Unknown WarpEngineType: {type}")
