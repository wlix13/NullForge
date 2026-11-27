"""Component base class bridging CLI commands and controllers."""

from typing import ClassVar, Generic

import rich_click as click

from nullforge.cli.core.types import ApplicationType, ControllerType


class BaseComponent(Generic[ApplicationType, ControllerType]):  # noqa: UP046
    """Base component — layer between CLI and Controller."""

    name: ClassVar[str]
    controller_class: ClassVar[type]
    expose_controller: ClassVar[bool] = True

    def __init__(self, app: ApplicationType) -> None:
        self.app = app
        self.controller: ControllerType = self.controller_class(app)

    @classmethod
    def expose_cli(cls, base: click.Group) -> None:
        """Register Click commands — to be implemented by subclasses."""

    def on_register(self) -> None:
        """Called after component is registered with application."""

    def on_deregister(self) -> None:
        """Called before component is deregistered from application."""
