"""Prepare the system for deployment."""

from nullforge.smithy.admin import is_root
from nullforge.smithy.packages import get_pm


def deploy_prepare() -> None:
    if is_root():
        _prepare_sudo()


def _prepare_sudo() -> None:
    """As some distros don't have sudo installed by default, we ensure to have it."""

    pm = get_pm()

    pm.update(
        name="Update package lists",
    )

    pm.install(
        name="Install minimal packages",
        packages=[
            "sudo",
            "locales",
        ],
    )


deploy_prepare()
