"""Swap configuration module."""

from pyinfra.context import host
from pyinfra.facts.files import File
from pyinfra.operations import files, server, systemd

from nullforge.models.system import SwapAlgo, SwapType
from nullforge.molds import SystemMold
from nullforge.smithy.packages import get_pm
from nullforge.templates import BLOCK_TRIM_ENV, get_template_path


def configure_swap(system: SystemMold) -> None:
    if not system.swap.enabled:
        _disable_swap()
        return

    _set_swappiness(system.swap.swappiness)

    if system.swap.type == SwapType.ZRAM:
        _disable_basic_swap()
        _configure_zram(system.swap.size, system.swap.algo)
    else:
        _disable_zram()
        _configure_basic_swap(system.swap.size)


def _disable_swap() -> None:
    _disable_basic_swap()
    _disable_zram()


def _disable_basic_swap() -> None:
    if host.get_fact(File, "/swapfile"):
        server.shell(
            name="Turn off swapfile",
            commands=["swapoff /swapfile"],
            _sudo=True,
        )

        files.file(
            name="Remove swapfile",
            path="/swapfile",
            present=False,
            _sudo=True,
        )

    files.line(
        name="Remove swapfile from fstab",
        path="/etc/fstab",
        line="/swapfile none swap sw 0 0",
        present=False,
        _sudo=True,
    )


def _disable_zram() -> None:
    pm = get_pm()
    pm.install(
        name="Remove zram-tools",
        packages=["zram-tools"],
        present=False,
        _sudo=True,
    )


def _set_swappiness(value: int) -> None:
    server.sysctl(
        name=f"Set swappiness to {value}",
        key="vm.swappiness",
        value=value,
        persist=True,
        persist_file="/etc/sysctl.d/99-swappiness.conf",
        _sudo=True,
    )


def _configure_zram(size: str, algo: SwapAlgo) -> None:
    pm = get_pm()
    pm.install(
        name="Install zram-tools",
        packages=["zram-tools"],
        _sudo=True,
    )

    zram_config = files.template(
        name="Configure zram-tools",
        src=get_template_path("etc/default/zramswap.j2"),
        dest="/etc/default/zramswap",
        mode="0644",
        jinja_env_kwargs=BLOCK_TRIM_ENV,
        algo=algo,
        size=size,
        _sudo=True,
    )

    systemd.service(
        name="Restart zramswap on change",
        service="zramswap",
        restarted=True,
        _sudo=True,
        _if=zram_config.did_change,
    )

    systemd.service(
        name="Ensure zramswap is running and enabled",
        service="zramswap",
        running=True,
        enabled=True,
        _sudo=True,
    )


def _configure_basic_swap(size: str) -> None:
    if not host.get_fact(File, "/swapfile"):
        server.shell(
            name=f"Create swapfile of size {size}",
            commands=[
                f"fallocate -l {size} /swapfile",
                "chmod 600 /swapfile",
                "mkswap /swapfile",
                "swapon /swapfile",
            ],
            _sudo=True,
        )

    files.line(
        name="Add swapfile to fstab",
        path="/etc/fstab",
        line="/swapfile none swap sw 0 0",
        _sudo=True,
    )
