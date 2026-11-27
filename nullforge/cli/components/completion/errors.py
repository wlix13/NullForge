"""Completion component errors."""

from nullforge.cli.core.errors import Error


class UnsupportedShell(Error):
    def __init__(self, shell: str) -> None:
        super().__init__(f"Unsupported shell [bold]{shell}[/bold].")


class ProfileNotFound(Error):
    def __init__(self, shell: str) -> None:
        super().__init__(f"Could not resolve [bold]{shell}[/bold] profile path.")
