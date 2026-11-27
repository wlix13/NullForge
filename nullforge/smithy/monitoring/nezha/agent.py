"""Nezha monitoring agent install builders."""

from __future__ import annotations

import shlex
import uuid


def agent_uuid_for_hostname(hostname: str, namespace: uuid.UUID | str | None = None) -> str:
    if not isinstance(hostname, (str, bytes)):
        hostname = str(hostname) if hostname is not None else ""
    if namespace is None:
        ns = uuid.NAMESPACE_DNS
    elif isinstance(namespace, uuid.UUID):
        ns = namespace
    else:
        ns = uuid.UUID(namespace)
    return str(uuid.uuid5(ns, hostname))


def build_nezha_install_command(
    *,
    install_url: str,
    curl_args: str,
    server: str,
    tls: bool,
    client_secret: str,
    agent_uuid: str,
    disable_auto_update: bool = False,
    disable_command_execute: bool = False,
) -> str:
    """Build shell one-liner that downloads and runs official Nezha agent installer."""

    env = {
        "NZ_SERVER": server,
        "NZ_TLS": "true" if tls else "false",
        "NZ_CLIENT_SECRET": client_secret,
        "NZ_UUID": agent_uuid,
        "NZ_DISABLE_AUTO_UPDATE": "true" if disable_auto_update else "false",
        "NZ_DISABLE_COMMAND_EXECUTE": "true" if disable_command_execute else "false",
    }
    env_str = " ".join(f"{key}={shlex.quote(value)}" for key, value in env.items())
    script = '"$script"'

    # if github download fails, retry the same install via mirror
    run_install = f"env {env_str} {script} || env CN=true {env_str} {script}"

    return (
        f"script=$(mktemp) "
        f"&& curl -L {curl_args} {shlex.quote(install_url)} -o {script} "
        f"&& chmod +x {script} "
        f"&& {{ {run_install}; }}; "
        f"rc=$?; rm -f {script}; exit $rc"
    )
