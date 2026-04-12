"""User management deployment module."""

import io
import shlex

from pyinfra.context import host
from pyinfra.facts.files import FileContents
from pyinfra.facts.server import Home
from pyinfra.operations import files, server

from nullforge.molds import FeaturesMold, UserMold
from nullforge.smithy.http import fetch_github_keys
from nullforge.smithy.packages import get_pm


def deploy_user_management() -> None:
    """Deploy user management configuration."""

    features: FeaturesMold = host.data.features
    user_opts: UserMold = features.users

    if user_opts.sudo:
        sudo_group = "sudo" if get_pm().is_debian_based else "wheel"
        groups = [sudo_group]
        operation_name = f"Create user {user_opts.name} with sudo access"
    else:
        groups = []
        operation_name = f"Create user {user_opts.name}"

    server.user(
        name=operation_name,
        user=user_opts.name,
        shell=user_opts.shell_path,
        groups=groups,
        append=True,
        create_home=True,
        _sudo=True,
    )

    if user_opts.password:
        _set_user_password(user_opts, user_opts.password)
    elif user_opts.sudo:
        _configure_passwordless_sudo(user_opts)

    if user_opts.copy_root_keys or user_opts.fetch_key_from_github:
        _install_ssh_keys(user_opts)

    if user_opts.set_root_shell_like_user:
        server.user(
            name="Set root shell to user's shell",
            user="root",
            shell=user_opts.shell_path,
            _sudo=True,
        )


def _set_user_password(opts: UserMold, password: str) -> None:
    """Set user password with protection against plaintext leakage."""

    creds_path = f"/root/.nullforge-chpasswd-{opts.name}"
    quoted_path = shlex.quote(creds_path)

    files.put(
        name=f"Stage credentials for user {opts.name}",
        src=io.StringIO(f"{opts.name}:{password}\n"),
        dest=creds_path,
        mode="0600",
        user="root",
        group="root",
        _sudo=True,
    )

    server.shell(
        name=f"Set password for user {opts.name}",
        commands=[f"chpasswd < {quoted_path}; rc=$?; rm -f {quoted_path}; exit $rc"],
        _sudo=True,
    )


def _configure_passwordless_sudo(opts: UserMold) -> None:
    """Configure passwordless sudo for user when no password is set."""

    username = opts.name
    sudoers_file = f"/etc/sudoers.d/{username}"
    sudoers_line = f"{username} ALL=(ALL) NOPASSWD:ALL"

    files.put(
        name=f"Configure passwordless sudo for {username}",
        src=io.StringIO(f"{sudoers_line}\n"),
        dest=sudoers_file,
        mode="0440",
        user="root",
        group="root",
        _sudo=True,
    )


def _dedup_keys(keys: list[str]) -> list[str]:
    """Deduplicate keys and remove blank lines and comments."""

    valid = (key.strip() for key in keys if key.strip() and not key.strip().startswith("#"))
    return list(dict.fromkeys(valid))


def _install_ssh_keys(opts: UserMold) -> None:
    """Install SSH keys for the user from root's authorized_keys and/or GitHub."""

    username = opts.name
    new_user_home = host.get_fact(Home, user=username)

    keys: list[str] = []

    if opts.copy_root_keys:
        current_user_home = host.get_fact(Home)
        keys.extend(host.get_fact(FileContents, f"{current_user_home}/.ssh/authorized_keys") or [])

    if opts.fetch_key_from_github:
        keys.extend(fetch_github_keys(opts.fetch_key_from_github))

    valid_keys = _dedup_keys(keys)

    if valid_keys:
        files.directory(
            name=f"Ensure SSH directory for {username}",
            path=f"{new_user_home}/.ssh",
            user=username,
            group=username,
            mode="0700",
            _sudo=True,
        )

        files.directory(
            name=f"Ensure SSH sockets directory for {username}",
            path=f"{new_user_home}/.ssh/sockets",
            user=username,
            group=username,
            mode="0700",
            _sudo=True,
        )

        server.user_authorized_keys(
            name=f"Add SSH keys for {username}",
            user=username,
            group=username,
            public_keys=valid_keys,
            _sudo=True,
        )

        files.file(
            name=f"Set SSH key permissions for {username}",
            path=f"{new_user_home}/.ssh/authorized_keys",
            user=username,
            group=username,
            mode="0600",
            _sudo=True,
        )


deploy_user_management()
