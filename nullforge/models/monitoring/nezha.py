"""Nezha monitoring backend layout."""

from typing import Literal

from .base import MonitoringBackendType, _MonitoringLayoutBase


class NezhaLayout(_MonitoringLayoutBase):
    type: Literal[MonitoringBackendType.NEZHA] = MonitoringBackendType.NEZHA
    base_dir: Literal["/opt/nezha/agent"] = "/opt/nezha/agent"
    binary_path: Literal["/opt/nezha/agent/nezha-agent"] = "/opt/nezha/agent/nezha-agent"
    config_path: Literal["/opt/nezha/agent/config.yml"] = "/opt/nezha/agent/config.yml"
    systemd_service_name: Literal["nezha-agent"] = "nezha-agent"
