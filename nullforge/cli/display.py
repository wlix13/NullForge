"""Display helper."""

from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any

from rich.table import Table

from nullforge.runes import RuneInfo


if TYPE_CHECKING:
    from nullforge.cli.core.application import BaseApplication


class Display:
    def __init__(self, app: "BaseApplication[Any]") -> None:
        self._app = app

    def __call__(self, *objects: Any, **kwargs: Any) -> None:
        self._app.console.print(*objects, **kwargs)

    def error(self, message: str) -> None:
        self._app.console_err.print(f"[red bold]Error:[/red bold] {message}")

    def aborted(self) -> None:
        self._app.console_err.print("[yellow]Aborted.[/yellow]")

    def runes_table(self, infos: Sequence[RuneInfo]) -> None:
        table = Table(title="Built-in runes")
        table.add_column("Rune", style="cyan bold", no_wrap=True)
        table.add_column("Summary")
        table.add_column("Path", style="dim")
        for info in infos:
            table.add_row(info.name, info.summary, str(info.path))
        self(table)

    def completion_installed(self, script: Path, profile: Path) -> None:
        self(f"[green]Installed:[/green] completion script [bold]{script}[/bold]")
        if profile != script:
            self(f"[green]Updated:[/green] profile [bold]{profile}[/bold]")
        self("[dim]Restart your shell to activate completion.[/dim]")
