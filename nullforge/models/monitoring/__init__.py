"""Monitoring configuration models."""

from typing import Annotated

from pydantic import Field

from .base import MonitoringBackendType, _MonitoringLayoutBase
from .nezha import NezhaLayout


MonitoringLayout = Annotated[NezhaLayout, Field(discriminator="type")]
"""Union-of-one for now. When second monitoring backend is added, extend union."""


def monitoring_layout_factory(type: MonitoringBackendType) -> MonitoringLayout:
    match type:
        case MonitoringBackendType.NEZHA:
            return NezhaLayout()
        case _:
            raise ValueError(f"Unknown MonitoringBackendType: {type}")


__all__ = [
    "MonitoringBackendType",
    "MonitoringLayout",
    "NezhaLayout",
    "_MonitoringLayoutBase",
    "monitoring_layout_factory",
]
