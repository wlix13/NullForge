"""Shared monitoring backend value types."""

from enum import StrEnum

from pydantic import BaseModel, Field


class MonitoringBackendType(StrEnum):
    NEZHA = "nezha"


class _MonitoringLayoutBase(BaseModel):
    """Static on-disk/service layout for monitoring agent backend."""

    type: MonitoringBackendType = Field(description="The monitoring backend type")
    base_dir: str | None = Field(..., description="The base/installation directory")
    binary_path: str | None = Field(..., description="The path to the binary")
    config_path: str | None = Field(..., description="The path to the configuration file")
    systemd_service_name: str | None = Field(..., description="The systemd service name")
