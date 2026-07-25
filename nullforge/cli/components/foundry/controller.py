"""Foundry controller for cast planning and Pyinfra execution."""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Final

from nullforge.cli.core import BaseController
from nullforge.foundry import FOUNDRY_DIR
from nullforge.runes import rune_path

from .errors import PyinfraExecutionFailed, PyinfraLaunchFailed


if TYPE_CHECKING:
    from nullforge.cli.app import NullForgeCli  # noqa: F401


@dataclass(slots=True)
class CastOptions:
    dry: bool = False
    diff: bool = False
    yes: bool = False
    sudo: bool = False
    debug: bool = False
    verbosity: int = 0
    ssh_user: str | None = None
    ssh_port: int | None = None
    ssh_key: str | None = None
    ssh_key_password: str | None = None
    ssh_password: str | None = None
    sudo_user: str | None = None
    su_user: str | None = None
    parallel: int | None = None
    limit: tuple[str, ...] = ()
    data: tuple[str, ...] = ()
    extra: tuple[str, ...] = ()


RUNES_DATA_KEY: Final[str] = "_nullforge_runes"

PYINFRA_RUNNER: Final[str] = "nullforge.foundry._pyinfra"
"""Launch Pyinfra through this wrapper instead of `-m pyinfra` to install display
patches (rune-stem labels) inside subprocess before Pyinfra renders any output.
"""

FLAG_OPTIONS: Final[tuple[tuple[str, str], ...]] = (
    ("dry", "--dry"),
    ("diff", "--diff"),
    ("yes", "-y"),
    ("sudo", "--sudo"),
    ("debug", "--debug"),
)
VALUE_OPTIONS: Final[tuple[tuple[str, str], ...]] = (
    ("ssh_user", "--ssh-user"),
    ("ssh_port", "--ssh-port"),
    ("ssh_key", "--ssh-key"),
    ("ssh_key_password", "--ssh-key-password"),
    ("ssh_password", "--ssh-password"),
    ("sudo_user", "--sudo-user"),
    ("su_user", "--su-user"),
    ("parallel", "--parallel"),
)
REPEAT_OPTIONS: Final[tuple[tuple[str, str], ...]] = (
    ("limit", "--limit"),
    ("data", "--data"),
)


class FoundryController(BaseController["NullForgeCli"]):
    def cast(
        self,
        inventory: str,
        runes: tuple[Path, ...],
        with_prepare: bool,
        options: CastOptions,
    ) -> None:
        """Run the resolved cast stages via Pyinfra."""

        for deploy_file, rune_paths in self.resolve_stages(runes, with_prepare):
            self._run_pyinfra(self.build_argv(inventory, deploy_file, rune_paths, options))

    def resolve_stages(self, runes: tuple[Path, ...], with_prepare: bool) -> list[tuple[Path, list[Path]]]:
        """Resolve (deploy_file, rune_paths) stages; prepare runs alone first so facts load after sudo exists."""

        cast_file = FOUNDRY_DIR / "cast.py"
        full_cast_file = FOUNDRY_DIR / "full_cast.py"
        prepare = rune_path("prepare")

        stages: list[tuple[Path, list[Path]]] = []
        if with_prepare:
            stages.append((cast_file, [prepare]))

        if not runes:
            stages.append((full_cast_file, []))
            return stages

        selected = list(dict.fromkeys(runes))
        if with_prepare:
            selected = [rune for rune in selected if rune != prepare]
        if selected:
            stages.append((cast_file, selected))
        return stages

    def build_argv(
        self,
        inventory: str,
        deploy_file: Path,
        rune_paths: list[Path],
        options: CastOptions,
    ) -> list[str]:
        """Build the Pyinfra argv for a single stage (run via the nullforge wrapper module)."""

        argv = [sys.executable, "-m", PYINFRA_RUNNER, inventory, str(deploy_file)]
        for field_name, flag in FLAG_OPTIONS:
            if getattr(options, field_name):
                argv.append(flag)
        argv.extend(["-v"] * options.verbosity)
        for field_name, flag in VALUE_OPTIONS:
            value = getattr(options, field_name)
            if value is not None:
                argv.extend([flag, str(value)])
        for field_name, flag in REPEAT_OPTIONS:
            for value in getattr(options, field_name):
                argv.extend([flag, value])
        if rune_paths:
            argv.extend(["--data", f"{RUNES_DATA_KEY}={json.dumps([str(path) for path in rune_paths])}"])
        argv.extend(options.extra)
        return argv

    def _run_pyinfra(self, argv: list[str]) -> None:
        """Run Pyinfra inheriting stdio, so its approval prompt reaches the TTY."""

        try:
            completed = subprocess.run(argv, check=False)  # noqa: S603
        except OSError as exc:
            raise PyinfraLaunchFailed.from_exc(exc) from exc
        if completed.returncode != 0:
            raise PyinfraExecutionFailed(completed.returncode)
