from collections.abc import Iterator

import pytest

from nullforge.cli.app import NullForgeCli
from nullforge.cli.core import BaseApplication


@pytest.fixture(autouse=True)
def _reset_singleton() -> Iterator[None]:
    BaseApplication.reset()
    NullForgeCli.reset()
    yield
    BaseApplication.reset()
    NullForgeCli.reset()


@pytest.fixture
def app() -> NullForgeCli:
    return NullForgeCli()
