"""Completion component and CLI commands."""

from __future__ import annotations

from typing import TYPE_CHECKING

import rich_click as click

from nullforge.cli.core import BaseComponent
from nullforge.cli.types import ShellType

from .controller import CompletionController


if TYPE_CHECKING:
    from nullforge.cli.app import NullForgeCli


class CompletionComponent(BaseComponent["NullForgeCli", CompletionController]):
    name = "completion"
    controller_class = CompletionController
    expose_controller = True

    @classmethod
    def expose_cli(cls, base: click.Group) -> None:
        @base.command()
        @click.argument("shell", type=ShellType())
        @click.option("--install", is_flag=True, help="Install the script into the shell profile.")
        @click.pass_obj
        def completion(app: NullForgeCli, shell: str, install: bool) -> None:
            """Print or install shell completion (bash, zsh, fish, powershell)."""

            if install:
                script_path, profile_path = app.completion.install(shell)
                app.display.completion_installed(script_path, profile_path)
            else:
                # Raw stdout on purpose: the rich console would wrap lines and corrupt the script.
                click.echo(app.completion.script(shell))
