"""Nezha dashboard REST client."""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from time import sleep
from typing import Any


LOG = logging.getLogger("pyinfra")

REGISTER_POLL_ATTEMPTS = 20
"""How many times to poll dashboard for freshly-registered agent."""

REGISTER_POLL_DELAY = 3
"""Seconds between registration polls."""

HTTP_TIMEOUT = 10
"""Request timeout, in seconds, for dashboard API calls."""

USER_AGENT = "nullforge-nezha-client/1.0"
"""Sent on every dashboard request."""


def _api_request(
    url: str,
    token: str,
    *,
    method: str = "GET",
    payload: dict[str, object] | None = None,
) -> dict[str, Any]:
    """Issue authenticated dashboard API request and return parsed envelope."""

    if not url.startswith(("https://", "http://")):
        raise ValueError(f"Refusing dashboard URL with unsupported scheme: {url}")
    if url.startswith("http://"):
        LOG.warning(f"Dashboard URL {url} is not HTTPS - the API token is sent in cleartext")

    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(url, data=data, method=method)  # noqa: S310 - scheme checked above
    request.add_header("Authorization", f"Bearer {token}")
    request.add_header("User-Agent", USER_AGENT)
    if data is not None:
        request.add_header("Content-Type", "application/json")

    try:
        with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT) as response:  # noqa: S310 - scheme checked above
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace").strip()
        raise RuntimeError(
            f"Dashboard API {method} {url} failed ({e.code} {e.reason}): {detail or '<empty body>'}"
        ) from e

    parsed: Any = json.loads(body) if body else {}
    if not isinstance(parsed, dict):
        raise ValueError(f"Unexpected dashboard response shape from {url}: {type(parsed)!r}")
    if parsed.get("success") is False:
        raise RuntimeError(f"Dashboard API error from {url}: {parsed.get('error', 'unknown error')}")
    return parsed


def _find_server(list_url: str, token: str, agent_uuid: str) -> tuple[int | None, str | None]:
    envelope = _api_request(list_url, token)
    servers = envelope.get("data")
    if not isinstance(servers, list):
        return None, None

    for entry in servers:
        if isinstance(entry, dict) and entry.get("uuid") == agent_uuid:
            server_id = entry.get("id")
            name = entry.get("name")
            if isinstance(server_id, int):
                return server_id, (name if isinstance(name, str) else None)
    return None, None


def server_name_matches(
    *,
    dashboard_url: str,
    api_token: str,
    agent_uuid: str,
    desired_name: str,
) -> bool:
    """Whether the dashboard already lists `agent_uuid` under `desired_name`."""

    try:
        server_id, current_name = _find_server(f"{dashboard_url}/api/v1/server", api_token, agent_uuid)
    except (RuntimeError, ValueError, OSError, json.JSONDecodeError) as e:
        LOG.warning(f"Could not read Nezha dashboard entry for {agent_uuid}: {e}")
        return False

    return server_id is not None and current_name == desired_name


def rename_nezha_server(
    *,
    dashboard_url: str,
    api_token: str,
    agent_uuid: str,
    desired_name: str,
) -> None:
    """Rename auto-registered dashboard entry for `agent_uuid` to `desired_name`."""

    list_url = f"{dashboard_url}/api/v1/server"

    server_id: int | None = None
    current_name: str | None = None
    for attempt in range(REGISTER_POLL_ATTEMPTS):
        # _api_request raises RuntimeError (with the dashboard's error body) on HTTP
        # errors such as 403; a hard failure propagates instead of pointlessly polling.
        server_id, current_name = _find_server(list_url, api_token, agent_uuid)
        if server_id is not None:
            break
        if attempt < REGISTER_POLL_ATTEMPTS - 1:
            sleep(REGISTER_POLL_DELAY)

    if server_id is None:
        LOG.warning(
            f"Nezha agent {agent_uuid} did not register within {REGISTER_POLL_ATTEMPTS * REGISTER_POLL_DELAY}s; "
            f"skipping rename to {desired_name}",
        )
        return

    if current_name == desired_name:
        return

    _api_request(
        f"{dashboard_url}/api/v1/server/{server_id}",
        api_token,
        method="PATCH",
        payload={"name": desired_name},
    )
    LOG.info(f"Renamed Nezha server {server_id} to {desired_name}")
