"""Monitoring configuration mold."""

from typing import Annotated

from pydantic import Field, model_validator

from nullforge.models.monitoring import MonitoringBackendType

from ..base_mold import BaseMold
from .nezha import NezhaBackend


MonitoringBackend = Annotated[NezhaBackend, Field(discriminator="type")]


class MonitoringMold(BaseMold):
    install: bool = Field(
        default=False,
        description="Whether to deploy monitoring agent",
    )
    backend: MonitoringBackend = Field(
        default_factory=NezhaBackend,
        description="Monitoring backend and its configuration",
    )

    @model_validator(mode="after")
    def _validate_install(self) -> "MonitoringMold":
        if self.install:
            self.backend.validate_enabled()
        return self

    @property
    def backend_type(self) -> MonitoringBackendType:
        return self.backend.type

    @property
    def is_active(self) -> bool:
        return self.install


__all__ = [
    "MonitoringBackend",
    "MonitoringMold",
    "NezhaBackend",
]
