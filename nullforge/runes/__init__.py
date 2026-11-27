"""Rune metadata."""

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Final


RUNES_DIR: Final[Path] = Path(__file__).parent


@dataclass(frozen=True, slots=True)
class RuneInfo:
    name: str
    path: Path
    summary: str


def rune_path(name: str) -> Path:
    """Absolute path of built-in rune."""

    return RUNES_DIR / f"{name}.py"


def rune_summary(path: Path) -> str:
    """First line of the rune docstring, extracted via ast."""

    try:
        module = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, ValueError):
        return ""
    docstring = ast.get_docstring(module)
    if not docstring:
        return ""
    return docstring.strip().splitlines()[0]


def discover_runes(directory: Path | None = None) -> tuple[RuneInfo, ...]:
    """Built-in runes: sorted *.py files in *directory*, skipping _-prefixed names."""

    directory = directory if directory is not None else RUNES_DIR
    try:
        candidates = sorted(path for path in directory.glob("*.py") if not path.name.startswith("_"))
    except OSError:
        return ()
    return tuple(RuneInfo(name=path.stem, path=path, summary=rune_summary(path)) for path in candidates)
