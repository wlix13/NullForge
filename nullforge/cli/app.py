"""NullForge CLI application and root command group."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

import rich_click as click

from nullforge import __version__
from nullforge.cli.components.completion.component import CompletionComponent
from nullforge.cli.components.completion.powershell import register_powershell_completion
from nullforge.cli.components.foundry.component import FoundryComponent
from nullforge.cli.components.runes.component import RunesComponent
from nullforge.cli.core import BaseApplication
from nullforge.cli.display import Display


if TYPE_CHECKING:
    from nullforge.cli.components.completion.controller import CompletionController
    from nullforge.cli.components.foundry.controller import FoundryController
    from nullforge.cli.components.runes.controller import RunesController

click.rich_click.USE_RICH_MARKUP = True
click.rich_click.SHOW_ARGUMENTS = True
click.rich_click.GROUP_ARGUMENTS_OPTIONS = True
click.rich_click.USE_MARKDOWN = False
click.rich_click.STYLE_ERRORS_SUGGESTION = "dim italic"
click.rich_click.MAX_WIDTH = 100

register_powershell_completion()


class NullForgeCli(BaseApplication["NullForgeCli"]):
    """Main application — component registry and dependency injector."""

    default_components = [FoundryComponent, RunesComponent, CompletionComponent]

    foundry: FoundryController
    runes: RunesController
    completion: CompletionController

    def __init__(self) -> None:
        self.display = Display(self)
        super().__init__()


@click.group(name="nullforge")
@click.version_option(__version__, "-V", "--version")
@click.pass_context
def cli(ctx: click.Context) -> None:
    """NullForge — forge the server's baseline from null."""

    app = NullForgeCli()
    app.cli_root = cast("click.Group", ctx.command)
    ctx.obj = app


NullForgeCli.register_cli(cli)
