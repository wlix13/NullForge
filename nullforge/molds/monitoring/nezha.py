"""Nezha monitoring backend configuration mold."""

from functools import cached_property
from typing import TYPE_CHECKING, ClassVar, Literal
from uuid import NAMESPACE_DNS, UUID, uuid5

from pydantic import Field, field_validator

from nullforge.models.monitoring import MonitoringBackendType, MonitoringLayout, monitoring_layout_factory

from ..base_mold import BaseMold


class NezhaBackend(BaseMold):
    """Per-host configuration for the Nezha monitoring agent."""

    _sensitive_fields: ClassVar[tuple[str, ...]] = ("client_secret", "api_token")

    type: Literal[MonitoringBackendType.NEZHA] = Field(
        default=MonitoringBackendType.NEZHA,
        description="Discriminator selecting Nezha backend",
    )
    server: str = Field(
        default="",
        description="Agent->dashboard data endpoint as host:port (NZ_SERVER)",
    )
    dashboard_url: str = Field(
        default="",
        description="Dashboard HTTP base URL used for API calls",
    )
    tls: bool = Field(
        default=True,
        description="Use TLS for agent data channel (NZ_TLS)",
    )
    client_secret: str = Field(
        default="",
        description="Per-user connection secret (NZ_CLIENT_SECRET)",
    )
    disable_auto_update: bool = Field(
        default=False,
        description="Disable agent's self-update (NZ_DISABLE_AUTO_UPDATE)",
    )
    disable_command_execute: bool = Field(
        default=True,
        description="Disable dashboard-initiated command execution (NZ_DISABLE_COMMAND_EXECUTE)",
    )
    set_name_to_hostname: bool = Field(
        default=True,
        description="Rename auto-registered dashboard entry to host hostname",
    )
    api_token: str = Field(
        default="",
        description="Dashboard PAT (nzp_...) for API calls",
    )
    uuid_namespace: UUID | None = Field(
        default=NAMESPACE_DNS,
        description=("Namespace for deterministic agent UUIDv5 dashboard-unique generation"),
    )

    if TYPE_CHECKING:
        # NOTE: This stub widens `uuid_namespace`
        # Keep the list in sync with the fields above when they change.
        def __init__(
            self,
            *,
            type: Literal[MonitoringBackendType.NEZHA] = MonitoringBackendType.NEZHA,
            server: str = "",
            dashboard_url: str = "",
            tls: bool = True,
            client_secret: str = "",
            disable_auto_update: bool = False,
            disable_command_execute: bool = True,
            set_name_to_hostname: bool = True,
            api_token: str = "",
            uuid_namespace: UUID | str | None = NAMESPACE_DNS,
        ) -> None: ...

    @field_validator("server", "dashboard_url", "client_secret", "api_token")
    @classmethod
    def _strip(cls, v: str) -> str:
        return v.strip()

    @field_validator("dashboard_url")
    @classmethod
    def _validate_dashboard_url(cls, v: str) -> str:
        v = v.rstrip("/")
        if v and not v.startswith("https://"):
            raise ValueError("dashboard_url must start with https://")
        return v

    @field_validator("uuid_namespace", mode="before")
    @classmethod
    def _coerce_uuid_namespace(cls, v: object) -> UUID | None:
        if v is None or isinstance(v, UUID):
            return v
        if isinstance(v, str):
            v = v.strip()
            if not v:
                return None
            try:
                return UUID(v)
            except ValueError:
                return uuid5(UUID(int=0), v)
        raise TypeError("uuid_namespace must be UUID, string, or None")

    def validate_enabled(self) -> None:
        """Assert config is complete enough to deploy."""

        if not self.server:
            raise ValueError("server is required when install is True")
        if not self.client_secret:
            raise ValueError("client_secret is required when install is True")
        if self.set_name_to_hostname and (not self.dashboard_url or not self.api_token):
            raise ValueError("dashboard_url and api_token are required when set_name_to_hostname is True")

    @cached_property
    def layout(self) -> MonitoringLayout:
        return monitoring_layout_factory(self.type)
