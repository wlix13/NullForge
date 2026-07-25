"""Framework-level errors."""


class Error(Exception):
    """Base error for the NullForge CLI. Uses rich markup for terminal display."""

    def __init__(self, message: str) -> None:
        super().__init__(f"[red]{message}[/red]")


class ComponentAlreadyRegistered(Error):
    def __init__(self, name: str) -> None:
        super().__init__(f"Component [bold]{name}[/bold] is already registered.")


class ComponentNotRegistered(Error):
    def __init__(self, name: str) -> None:
        super().__init__(f"Component [bold]{name}[/bold] is not registered.")


class Unreachable(Error):
    def __init__(self) -> None:
        super().__init__("Reached unreachable code.")
