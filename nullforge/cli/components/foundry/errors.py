"""Foundry component errors."""

from nullforge.cli.core.errors import Error


class PyinfraExecutionFailed(Error):
    def __init__(self, returncode: int) -> None:
        self.returncode = returncode
        super().__init__(f"Pyinfra exited with code [bold]{returncode}[/bold].")


class PyinfraLaunchFailed(Error):
    @classmethod
    def from_exc(cls, exc: OSError) -> "PyinfraLaunchFailed":
        return cls(f"Failed to launch Pyinfra: {exc}")
