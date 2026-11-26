"""User management deployment module."""

import io
import shlex

from pyinfra.context import host
from pyinfra.facts.files import File, FileContents
from pyinfra.facts.server import Home, Users
from pyinfra.operations import files, server

from nullforge.models.users import UserRole
from nullforge.molds import FeaturesMold, UserMold
from nullforge.molds.user import _sudoers_filename
from nullforge.smithy.http import fetch_github_keys
from nullforge.smithy.packages import get_pm


def deploy_user_management() -> None:
    """Deploy user management configuration."""

    features: FeaturesMold = host.data.features

    for user_opts in host.loop(features.users):
        _deploy_user(user_opts)

        if user_opts.set_root_shell_like_user:
            server.user(
                name=f"Set root shell to {user_opts.name}'s shell",
                user="root",
                shell=user_opts.shell_path,
                _sudo=True,
            )


def _deploy_user(opts: UserMold) -> None:
    role = opts.role

    if role is UserRole.ADMIN:
        sudo_group = "sudo" if get_pm().is_debian_based else "wheel"
        groups = [sudo_group]
        append = True
        operation_name = f"Create user {opts.name} with sudo access"
    else:
        groups = []
        append = False
        operation_name = f"Create user {opts.name}"

    server.user(
        name=operation_name,
        user=opts.name,
        shell=opts.shell_path,
        groups=groups,
        append=append,
        create_home=True,
        _sudo=True,
    )

    # Strip sudo/wheel group when downgrading from ADMIN to DEPLOY/NONE
    if role in (UserRole.DEPLOY, UserRole.NONE):
        sudo_group = "sudo" if get_pm().is_debian_based else "wheel"
        users_fact = host.get_fact(Users)
        if users_fact and opts.name in users_fact:
            user_groups = users_fact[opts.name].get("groups", [])
            if sudo_group in user_groups:
                server.shell(
                    name=f"Remove {opts.name} from {sudo_group} group",
                    commands=[f"gpasswd -d {opts.name} {sudo_group}"],
                    _sudo=True,
                )

    if opts.password:
        _set_user_password(opts)

    if role is UserRole.ADMIN and not opts.password:
        _configure_passwordless_sudo(opts)
    elif role is UserRole.DEPLOY and opts.sudo_commands:
        _configure_passwordless_sudo(opts, opts.sudo_commands)
    else:
        _remove_sudoers_dropin(opts)

    if opts.ssh_keys or opts.copy_root_keys or opts.fetch_key_from_github:
        _install_ssh_keys(opts)


def _set_user_password(opts: UserMold) -> None:
    """Set user password with protection against plaintext leakage."""

    username = opts.name
    password = opts.password
    creds_path = f"/root/.nullforge-chpasswd-{username}"
    quoted_path = shlex.quote(creds_path)

    files.put(
        name=f"Stage credentials for user {username}",
        src=io.StringIO(f"{username}:{password}\n"),
        dest=creds_path,
        mode="0600",
        user="root",
        group="root",
        _sudo=True,
    )

    server.shell(
        name=f"Set password for user {username}",
        commands=[f"chpasswd < {quoted_path}; rc=$?; rm -f {quoted_path}; exit $rc"],
        _sudo=True,
    )


def _remove_sudoers_dropin(opts: UserMold) -> None:
    username = opts.name
    sudoers_file = f"/etc/sudoers.d/{_sudoers_filename(username)}"
    if host.get_fact(File, sudoers_file, _sudo=True):
        files.file(
            name=f"Remove passwordless sudo drop-in for {username}",
            path=sudoers_file,
            present=False,
            _sudo=True,
        )


def _configure_passwordless_sudo(opts: UserMold, commands: list[str] | None = None) -> None:
    """Configure passwordless sudo for user when no password is set."""

    username = opts.name
    sudoers_file = f"/etc/sudoers.d/{_sudoers_filename(username)}"
    if commands is None:
        sudoers_line = f"{username} ALL=(ALL) NOPASSWD:ALL"
    else:
        sudoers_line = f"{username} ALL=(ALL) NOPASSWD: {', '.join(commands)}"

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

    if opts.ssh_keys:
        keys.extend(opts.ssh_keys)

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
