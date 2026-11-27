"""Custom Click parameter types."""

from pathlib import Path
from typing import Final

import click
from click.shell_completion import CompletionItem

from nullforge.runes import discover_runes, rune_path


SUPPORTED_SHELLS: Final[tuple[str, ...]] = ("bash", "fish", "powershell", "zsh")

SHELL_ALIASES: Final[dict[str, str]] = {"pwsh": "powershell"}


def _looks_like_path(value: str) -> bool:
    return value.endswith(".py") or "/" in value or "\\" in value


def _split_incomplete(incomplete: str) -> tuple[Path, str, str]:
    """Split an incomplete path into (directory to list, prefix to keep, name fragment)."""

    cut = max(incomplete.rfind("/"), incomplete.rfind("\\"))
    if cut < 0:
        return Path(), "", incomplete
    prefix, fragment = incomplete[: cut + 1], incomplete[cut + 1 :]
    return Path(prefix.replace("\\", "/")).expanduser(), prefix, fragment


def complete_paths(incomplete: str, *, suffixes: tuple[str, ...] = (".py",)) -> list[CompletionItem]:
    """Complete directories and files matching suffixes, preserving the typed separator style."""

    directory, prefix, fragment = _split_incomplete(incomplete)
    separator = "\\" if "\\" in prefix else "/"
    try:
        entries = sorted(directory.iterdir(), key=lambda entry: (entry.is_file(), entry.name.lower()))
    except OSError:
        return []
    items: list[CompletionItem] = []
    for entry in entries:
        if not entry.name.startswith(fragment):
            continue
        if entry.is_dir():
            items.append(CompletionItem(f"{prefix}{entry.name}{separator}"))
        elif entry.suffix.lower() in suffixes:
            items.append(CompletionItem(f"{prefix}{entry.name}"))
    return items


class InventoryType(click.ParamType):
    """Pyinfra inventory .py file or raw host spec (@local, host1,host2)."""

    name = "inventory"

    def convert(self, value: str, param: click.Parameter | None, ctx: click.Context | None) -> str:
        path = Path(value).expanduser()
        if path.is_file():
            return str(path.resolve())
        if _looks_like_path(value):
            self.fail(f"Inventory file {value!r} not found.", param, ctx)
        return value

    def shell_complete(self, ctx: click.Context, param: click.Parameter, incomplete: str) -> list[CompletionItem]:
        items = complete_paths(incomplete)
        if "@local".startswith(incomplete):
            items.append(CompletionItem("@local", help="Run against this machine"))
        return items


class RuneType(click.ParamType):
    """Built-in rune name or path to a custom rune .py file."""

    name = "rune"

    def convert(self, value: str, param: click.Parameter | None, ctx: click.Context | None) -> Path:
        if _looks_like_path(value):
            path = Path(value).expanduser()
            if not path.is_file():
                self.fail(f"Rune file {value!r} not found.", param, ctx)
            return path.resolve()
        builtin = rune_path(value)
        if value.startswith("_") or not builtin.is_file():
            known = ", ".join(info.name for info in discover_runes())
            self.fail(f"Unknown rune {value!r}. Built-in runes: {known}.", param, ctx)
        return builtin

    def shell_complete(self, ctx: click.Context, param: click.Parameter, incomplete: str) -> list[CompletionItem]:
        if _looks_like_path(incomplete):
            return complete_paths(incomplete)
        return [
            CompletionItem(info.name, help=info.summary)
            for info in discover_runes()
            if info.name.startswith(incomplete)
        ]


class ShellType(click.ParamType):
    """Shell supported for completion script generation."""

    name = "shell"

    def convert(self, value: str, param: click.Parameter | None, ctx: click.Context | None) -> str:
        shell = SHELL_ALIASES.get(value.lower(), value.lower())
        if shell not in SUPPORTED_SHELLS:
            self.fail(f"Unsupported shell {value!r}. Supported: {', '.join(SUPPORTED_SHELLS)}.", param, ctx)
        return shell

    def shell_complete(self, ctx: click.Context, param: click.Parameter, incomplete: str) -> list[CompletionItem]:
        return [CompletionItem(shell) for shell in SUPPORTED_SHELLS if shell.startswith(incomplete.lower())]


class KeyValueType(click.ParamType):
    """Key=value pair passed through to Pyinfra --data."""

    name = "key=value"

    def convert(self, value: str, param: click.Parameter | None, ctx: click.Context | None) -> str:
        key, sep, _ = value.partition("=")
        if not sep or not key:
            self.fail(f"Expected key=value, got {value!r}.", param, ctx)
        return value
