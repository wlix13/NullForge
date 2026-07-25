"""Type variables shared by the CLI framework."""

from __future__ import annotations

from typing import TYPE_CHECKING, TypeVar


if TYPE_CHECKING:
    from nullforge.cli.core.application import BaseApplication
    from nullforge.cli.core.controller import BaseController

ApplicationType = TypeVar("ApplicationType", bound="BaseApplication")
ControllerType = TypeVar("ControllerType", bound="BaseController")
