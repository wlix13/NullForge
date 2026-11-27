"""Shared helpers for provisioning system service users and config directories."""

from pyinfra.context import host
from pyinfra.facts.server import Groups, Users
from pyinfra.operations import files, server


def ensure_service_user(user: str, group: str, config_dir: str) -> None:
    """Ensure a system service user, group, and config directory exist."""

    if group not in host.get_fact(Groups):
        server.group(
            name=f"Ensure {group} group exists",
            group=group,
            system=True,
            _sudo=True,
        )

    if user not in host.get_fact(Users):
        server.user(  # noqa: S604
            name=f"Ensure {user} system user exists",
            user=user,
            system=True,
            group=group,
            shell="/bin/false",
            create_home=False,
            _sudo=True,
        )

    files.directory(
        name=f"Ensure {config_dir} configuration directory exists",
        path=config_dir,
        user=user,
        group=group,
        mode="0755",
        _sudo=True,
    )
