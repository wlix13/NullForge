"""Nezha agent deploy orchestration."""

from pyinfra.context import host
from pyinfra.facts.files import File
from pyinfra.facts.server import Hostname
from pyinfra.operations import python, server, systemd

from nullforge.molds.monitoring import NezhaBackend
from nullforge.molds.system import SystemMold
from nullforge.smithy.http import curl_args_str
from nullforge.smithy.versions import STATIC_URLS

from .agent import agent_uuid_for_hostname, build_nezha_install_command
from .dashboard import rename_nezha_server, server_name_matches


def _resolve_hostname(cfg: NezhaBackend) -> str:
    system: SystemMold = host.data.system
    if isinstance(system.hostname, str) and system.hostname:
        return system.hostname

    fact = host.get_fact(Hostname)
    if isinstance(fact, str) and fact:
        return fact
    return cfg.layout.systemd_service_name


def deploy_nezha(cfg: NezhaBackend) -> None:
    """Deploy Nezha agent and align dashboard name with hostname."""

    layout = cfg.layout
    hostname = _resolve_hostname(cfg)
    agent_uuid = agent_uuid_for_hostname(hostname, namespace=cfg.uuid_namespace)

    if not host.get_fact(File, layout.config_path):
        install_command = build_nezha_install_command(
            install_url=STATIC_URLS["nezha_agent_install"],
            curl_args=curl_args_str(STATIC_URLS["nezha_agent_install"]),
            server=cfg.server,
            tls=cfg.tls,
            client_secret=cfg.client_secret,
            agent_uuid=agent_uuid,
            disable_auto_update=cfg.disable_auto_update,
            disable_command_execute=cfg.disable_command_execute,
        )
        server.shell(
            name="Install Nezha agent",
            commands=[install_command],
            _sudo=True,
            _retries=3,
            _retry_delay=10,
        )

    systemd.service(
        name="Ensure Nezha agent is running",
        service=layout.systemd_service_name,
        running=True,
        enabled=True,
        _sudo=True,
    )

    if not cfg.set_name_to_hostname:
        return

    if server_name_matches(
        dashboard_url=cfg.dashboard_url,
        api_token=cfg.api_token,
        agent_uuid=agent_uuid,
        desired_name=hostname,
    ):
        host.noop(f"Nezha dashboard already names {agent_uuid} '{hostname}'")
        return

    python.call(
        name="Set Nezha dashboard name to hostname",
        function=rename_nezha_server,
        dashboard_url=cfg.dashboard_url,
        api_token=cfg.api_token,
        agent_uuid=agent_uuid,
        desired_name=hostname,
    )
