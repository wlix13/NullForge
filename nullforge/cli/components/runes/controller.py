"""Runes controller for listing built-in runes."""

from __future__ import annotations

from typing import TYPE_CHECKING

from nullforge.cli.core import BaseController
from nullforge.runes import discover_runes


if TYPE_CHECKING:
    from nullforge.cli.app import NullForgeCli  # noqa: F401


class RunesController(BaseController["NullForgeCli"]):
    def list_runes(self) -> None:
        """Display the built-in rune table."""

        self.app.display.runes_table(discover_runes())
