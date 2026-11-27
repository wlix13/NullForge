"""Completion controller for script generation and installation."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Final

from click.shell_completion import get_completion_class

from nullforge.cli.core import BaseController
from nullforge.cli.core.errors import Unreachable

from .errors import ProfileNotFound, UnsupportedShell


if TYPE_CHECKING:
    from nullforge.cli.app import NullForgeCli  # noqa: F401

COMPLETE_VAR: Final[str] = "_NULLFORGE_COMPLETE"
PROG_NAME: Final[str] = "nullforge"

MARKER_BEGIN: Final[str] = "# >>> nullforge completion >>>"
MARKER_END: Final[str] = "# <<< nullforge completion <<<"

SCRIPT_SUFFIXES: Final[dict[str, str]] = {
    "bash": "bash",
    "zsh": "zsh",
    "fish": "fish",
    "powershell": "ps1",
}


class CompletionController(BaseController["NullForgeCli"]):
    def script(self, shell: str) -> str:
        """Generate the completion script for shell."""

        completion_cls = get_completion_class(shell)
        if completion_cls is None:
            raise UnsupportedShell(shell)
        if self.app.cli_root is None:
            raise Unreachable()
        return completion_cls(self.app.cli_root, {}, PROG_NAME, COMPLETE_VAR).source()

    def install(self, shell: str) -> tuple[Path, Path]:
        """Write the completion script and wire it into the shell profile. Idempotent."""

        script_path = self._script_path(shell)
        script_path.parent.mkdir(parents=True, exist_ok=True)
        script_path.write_text(self.script(shell), encoding="utf-8")
        if shell == "fish":
            return script_path, script_path  # fish autoloads from completions/, no profile edit

        profile_path = self._profile_path(shell)
        existing = profile_path.read_text(encoding="utf-8") if profile_path.exists() else ""
        if MARKER_BEGIN not in existing:
            profile_path.parent.mkdir(parents=True, exist_ok=True)
            block = f"\n{MARKER_BEGIN}\n{self._source_line(shell, script_path)}\n{MARKER_END}\n"
            with profile_path.open("a", encoding="utf-8") as handle:
                handle.write(block)
        return script_path, profile_path

    def _script_path(self, shell: str) -> Path:
        if shell == "fish":
            return Path.home() / ".config" / "fish" / "completions" / "nullforge.fish"
        return Path.home() / ".nullforge" / f"completion.{SCRIPT_SUFFIXES[shell]}"

    def _source_line(self, shell: str, script_path: Path) -> str:
        if shell == "powershell":
            return f'. "{script_path}"'
        return f'source "{script_path}"'

    def _profile_path(self, shell: str) -> Path:
        if shell == "bash":
            return Path.home() / ".bashrc"
        if shell == "zsh":
            return Path.home() / ".zshrc"
        if shell == "powershell":
            return self._powershell_profile()
        raise Unreachable()

    def _powershell_profile(self) -> Path:
        executable = shutil.which("pwsh") or shutil.which("powershell")
        if executable is None:
            raise ProfileNotFound("powershell")
        try:
            completed = subprocess.run(  # noqa: S603
                [executable, "-NoProfile", "-Command", "$PROFILE"],
                capture_output=True,
                text=True,
                check=False,
            )
        except OSError as exc:
            raise ProfileNotFound("powershell") from exc
        profile = completed.stdout.strip()
        if completed.returncode != 0 or not profile:
            raise ProfileNotFound("powershell")
        return Path(profile)
