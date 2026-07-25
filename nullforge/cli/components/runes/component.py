"""Runes component and CLI commands."""

from __future__ import annotations

from typing import TYPE_CHECKING

import rich_click as click

from nullforge.cli.core import BaseComponent

from .controller import RunesController


if TYPE_CHECKING:
    from nullforge.cli.app import NullForgeCli


class RunesComponent(BaseComponent["NullForgeCli", RunesController]):
    name = "runes"
    controller_class = RunesController
    expose_controller = True

    @classmethod
    def expose_cli(cls, base: click.Group) -> None:
        @base.command()
        @click.pass_obj
        def runes(app: NullForgeCli) -> None:
            """List built-in runes."""

            app.runes.list_runes()
