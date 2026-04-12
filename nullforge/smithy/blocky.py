"""Blocky DNS proxy setup module."""

from pyinfra.api.operation import OperationMeta
from pyinfra.context import host
from pyinfra.operations import files

from nullforge.smithy.install import install_release_binary
from nullforge.smithy.versions import get_versions, is_pinned_version_installed


BLOCKY_GROUP = "blocky"
BLOCKY_USER = "blocky"
BLOCKY_BINARY = "/usr/bin/blocky"


def ensure_blocky_binary() -> OperationMeta | None:
    if is_pinned_version_installed("blocky", BLOCKY_BINARY):
        host.noop("blocky binary is already installed")
        return None

    install_op = install_release_binary(
        name="Install blocky binary",
        url=get_versions().blocky_tar(),
        dest=BLOCKY_BINARY,
        binary_name="blocky",
    )

    files.file(
        name="Set blocky binary permissions",
        path=BLOCKY_BINARY,
        mode="0755",
        user="root",
        group=BLOCKY_GROUP,
        _sudo=True,
    )

    return install_op
