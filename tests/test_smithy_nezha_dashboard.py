import urllib.request
from typing import Any

import pytest

from nullforge.smithy.monitoring.nezha import dashboard as nezha_dashboard


class _FakeResponse:
    def __init__(self, body: bytes) -> None:
        self._body = body

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def read(self) -> bytes:
        return self._body


class TestApiRequest:
    def test_sets_non_default_user_agent(self, monkeypatch: pytest.MonkeyPatch) -> None:
        captured: dict[str, Any] = {}

        def fake_urlopen(request: urllib.request.Request, timeout: float = 0) -> _FakeResponse:
            captured["ua"] = request.get_header("User-agent")
            return _FakeResponse(b'{"success": true, "data": []}')

        monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
        nezha_dashboard._api_request("https://dash.example.com/api/v1/server", "tok")

        # Cloudflare-fronted dashboards 403 the default Python-urllib agent.
        assert captured["ua"] == nezha_dashboard.USER_AGENT
        assert "python-urllib" not in captured["ua"].lower()


class TestRenameNezhaServer:
    def test_patches_when_name_differs(self, monkeypatch: pytest.MonkeyPatch) -> None:
        calls: list[tuple[str, str, dict[str, object] | None]] = []

        def fake_api(url: str, token: str, *, method: str = "GET", payload=None):  # noqa: ANN001, ANN202
            calls.append((url, method, payload))
            if method == "GET":
                return {"success": True, "data": [{"id": 7, "uuid": "u", "name": "petname-here"}]}
            return {"success": True}

        monkeypatch.setattr(nezha_dashboard, "_api_request", fake_api)
        nezha_dashboard.rename_nezha_server(
            dashboard_url="https://dash.example.com",
            api_token="t",
            agent_uuid="u",
            desired_name="node-1",
        )

        patch_calls = [c for c in calls if c[1] == "PATCH"]
        assert patch_calls == [("https://dash.example.com/api/v1/server/7", "PATCH", {"name": "node-1"})]

    def test_idempotent_when_name_matches(self, monkeypatch: pytest.MonkeyPatch) -> None:
        calls: list[str] = []

        def fake_api(url: str, token: str, *, method: str = "GET", payload=None):  # noqa: ANN001, ANN202
            calls.append(method)
            return {"success": True, "data": [{"id": 7, "uuid": "u", "name": "node-1"}]}

        monkeypatch.setattr(nezha_dashboard, "_api_request", fake_api)
        nezha_dashboard.rename_nezha_server(
            dashboard_url="https://dash.example.com", api_token="t", agent_uuid="u", desired_name="node-1"
        )
        assert "PATCH" not in calls

    def test_skips_when_unregistered(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(nezha_dashboard, "REGISTER_POLL_ATTEMPTS", 1)
        monkeypatch.setattr(nezha_dashboard, "REGISTER_POLL_DELAY", 0)

        def fake_api(url: str, token: str, *, method: str = "GET", payload=None):  # noqa: ANN001, ANN202
            return {"success": True, "data": []}

        monkeypatch.setattr(nezha_dashboard, "_api_request", fake_api)
        # must not raise — unregistered agent is logged and skipped
        nezha_dashboard.rename_nezha_server(
            dashboard_url="https://dash.example.com", api_token="t", agent_uuid="u", desired_name="node-1"
        )
