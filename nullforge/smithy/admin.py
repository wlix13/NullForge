"""Admin utilities for NullForge."""

from pyinfra.context import host
from pyinfra.facts.server import Command, User
from pyinfra.operations import server


def is_root() -> bool:
    cache_key = "_nullforge_is_root"
    if hasattr(host.data, cache_key):
        return getattr(host.data, cache_key)

    result = host.get_fact(User) == "root"

    setattr(host.data, cache_key, result)
    return result


def _acl_entries(path: str) -> str:
    return host.get_fact(Command, f"getfacl {path} 2>/dev/null || true", _sudo=True) or ""


def ensure_acl_access(username: str, directory: str, rw_files: list[str] | None = None) -> None:
    """Grant a user rwx ACL access to a directory, and optional rw to specific files."""

    cmds: list[str] = []

    if f"user:{username}:rwx" not in _acl_entries(directory):
        cmds += [
            f"setfacl -m u:{username}:rwx {directory}",
            f"setfacl -d -m u:{username}:rwx {directory}",
        ]

    for f in rw_files or []:
        entries = _acl_entries(f)
        if entries and f"user:{username}:rw" not in entries:
            cmds.append(f"setfacl -m u:{username}:rw {f}")

    if cmds:
        server.shell(name=f"Set ACLs on {directory}", commands=cmds, _sudo=True)
