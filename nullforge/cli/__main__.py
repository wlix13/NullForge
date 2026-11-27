"""NullForge CLI entry point."""

from click.exceptions import Abort, ClickException, Exit
from rich.console import Console

from nullforge.cli.app import cli
from nullforge.cli.components.foundry.errors import PyinfraExecutionFailed
from nullforge.cli.core import Error


_err = Console(stderr=True)


def main() -> None:
    try:
        cli(standalone_mode=False, prog_name="nullforge")
    except PyinfraExecutionFailed as e:
        _err.print(f"[red bold]Error:[/red bold] {e}")
        raise SystemExit(e.returncode)
    except Error as e:
        _err.print(f"[red bold]Error:[/red bold] {e}")
        raise SystemExit(1)
    except ClickException as e:
        e.show()
        raise SystemExit(e.exit_code)
    except Exit as e:
        raise SystemExit(e.exit_code)
    except SystemExit:
        raise
    except Abort:
        _err.print("\n[yellow]Aborted.[/yellow]")
        raise SystemExit(130)
    except KeyboardInterrupt:
        _err.print("\n[yellow]Interrupted.[/yellow]")
        raise SystemExit(130)
    except Exception as e:
        _err.print(f"[red bold]Unexpected error:[/red bold] {e}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
