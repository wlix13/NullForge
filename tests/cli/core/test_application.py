from typing import Any, ClassVar

import click
import pytest

from nullforge.cli.core import BaseApplication, BaseComponent, BaseController
from nullforge.cli.core.errors import ComponentAlreadyRegistered, ComponentNotRegistered


class CountingController(BaseController[Any]):
    pass


class CountingComponent(BaseComponent[Any, CountingController]):
    name = "counting"
    controller_class = CountingController
    expose_controller = True

    registered: ClassVar[int] = 0
    deregistered: ClassVar[int] = 0

    def on_register(self) -> None:
        type(self).registered += 1

    def on_deregister(self) -> None:
        type(self).deregistered += 1


def _counting_component() -> type[CountingComponent]:
    """Fresh subclass per test: type(self) counters shadow the parent's zeros."""

    class FreshCountingComponent(CountingComponent):
        pass

    return FreshCountingComponent


def test_register_exposes_controller_and_fires_hook() -> None:
    component_cls = _counting_component()
    app = BaseApplication[Any]()

    app.register(component_cls)

    assert component_cls.registered == 1
    assert "counting" in app.components
    assert isinstance(getattr(app, "counting"), CountingController)  # noqa: B009


def test_register_duplicate_name_raises() -> None:
    component_cls = _counting_component()
    app = BaseApplication[Any]()
    app.register(component_cls)

    with pytest.raises(ComponentAlreadyRegistered):
        app.register(component_cls)


def test_deregister_fires_hook_and_removes_controller() -> None:
    component_cls = _counting_component()
    app = BaseApplication[Any]()
    app.register(component_cls)

    app.deregister("counting")

    assert component_cls.deregistered == 1
    assert not hasattr(app, "counting")
    assert "counting" not in app.components


def test_deregister_unknown_raises() -> None:
    app = BaseApplication[Any]()

    with pytest.raises(ComponentNotRegistered):
        app.deregister("counting")


def test_current_requires_initialization() -> None:
    with pytest.raises(RuntimeError):
        BaseApplication.current()

    app = BaseApplication[Any]()
    assert BaseApplication.current() is app


def test_reinitialization_replaces_singleton() -> None:
    BaseApplication[Any]()
    second = BaseApplication[Any]()

    assert BaseApplication.current() is second


def test_reset_clears_singleton() -> None:
    BaseApplication[Any]()

    BaseApplication.reset()

    with pytest.raises(RuntimeError):
        BaseApplication.current()


def test_register_cli_visits_default_components_in_order() -> None:
    visited: list[str] = []

    class FirstComponent(BaseComponent[Any, BaseController[Any]]):
        name = "first"
        controller_class = BaseController

        @classmethod
        def expose_cli(cls, base: click.Group) -> None:
            visited.append(cls.name)

    class SecondComponent(FirstComponent):
        name = "second"

    class RecordingApp(BaseApplication["RecordingApp"]):
        default_components = [FirstComponent, SecondComponent]

    RecordingApp.register_cli(click.Group("root"))

    assert visited == ["first", "second"]
