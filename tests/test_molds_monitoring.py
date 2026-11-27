import uuid
from typing import Any

import pytest
from pydantic import ValidationError

from nullforge.molds.monitoring import MonitoringMold, NezhaBackend


def _valid(**overrides: object) -> dict[str, Any]:
    backend: dict[str, object] = {
        "type": "nezha",
        "server": "agent.status.example.com:443",
        "client_secret": "secret",
        "dashboard_url": "https://dash.example.com",
        "api_token": "nzp_token",
    }
    backend.update(overrides)
    return {"install": True, "backend": backend}


class TestValidation:
    def test_install_requires_server(self) -> None:
        with pytest.raises(ValidationError, match="server is required"):
            MonitoringMold(**_valid(server=""))

    def test_install_requires_secret(self) -> None:
        with pytest.raises(ValidationError, match="client_secret is required"):
            MonitoringMold(**_valid(client_secret=""))

    def test_rename_requires_dashboard_and_token(self) -> None:
        with pytest.raises(ValidationError, match="dashboard_url and api_token"):
            MonitoringMold(**_valid(dashboard_url=""))

    def test_rename_disabled_relaxes_requirements(self) -> None:
        mold = MonitoringMold(
            install=True,
            backend=NezhaBackend(server="x:443", client_secret="s", set_name_to_hostname=False),
        )
        assert mold.backend.set_name_to_hostname is False

    def test_dashboard_url_scheme_enforced(self) -> None:
        with pytest.raises(ValidationError, match="http"):
            MonitoringMold(**_valid(dashboard_url="dash.example.com"))

    def test_dashboard_url_trailing_slash_stripped(self) -> None:
        mold = MonitoringMold(**_valid(dashboard_url="https://dash.example.com/"))
        assert mold.backend.dashboard_url == "https://dash.example.com"

    def test_uuid_namespace_accepts_uuid_string(self) -> None:
        ns = uuid.uuid4()
        backend = NezhaBackend(uuid_namespace=str(ns))
        assert backend.uuid_namespace == ns

    def test_uuid_namespace_derives_from_freeform_string(self) -> None:
        backend = NezhaBackend(uuid_namespace="not-a-uuid")
        assert backend.uuid_namespace == uuid.uuid5(uuid.UUID(int=0), "not-a-uuid")

    def test_uuid_namespace_empty_string_is_none(self) -> None:
        assert NezhaBackend(uuid_namespace="").uuid_namespace is None

    def test_disabled_install_skips_validation(self) -> None:
        # install=False should not require any connection fields
        assert MonitoringMold(install=False).install is False


class TestRedaction:
    def test_to_json_masks_secrets(self) -> None:
        mold = MonitoringMold(**_valid())
        backend = mold.to_json()["backend"]
        assert backend["client_secret"] == "***"
        assert backend["api_token"] == "***"
        assert backend["server"] == "agent.status.example.com:443"

    def test_model_dump_keeps_secrets_for_deploy(self) -> None:
        # the merge pipeline relies on real values via model_dump, not to_json
        mold = MonitoringMold(**_valid())
        assert mold.model_dump()["backend"]["client_secret"] == "secret"
