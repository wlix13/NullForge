from unittest.mock import MagicMock, patch

import pyinfra.local as _pyinfra_local
import pytest
from pyinfra.facts.server import Hostname

from nullforge.molds.defaults import BASE_FEATURES, BASE_SYSTEM
from nullforge.molds.utils import ensure_features, ensure_system


_mock_host = MagicMock()
_mock_host.data.features = ensure_features(BASE_FEATURES.model_copy())
system = ensure_system(BASE_SYSTEM.model_copy())
system.hostname = "nullforge.test"
_mock_host.data.system = system
_mock_host.data._nullforge_supported_locales = ["en_US.UTF-8 UTF-8"]


def _get_fact(fact: object, *args: object, **kwargs: object) -> object:
    """Return values for pyinfra facts during tests."""

    if fact is Hostname or getattr(fact, "__name__", None) == "Hostname":
        return "nullforge.test"
    return MagicMock()


_mock_host.get_fact.side_effect = _get_fact
_mock_host.loop.side_effect = lambda iterable: iter(iterable)

_ops = MagicMock()

_patchers = [
    patch("pyinfra.context.host", _mock_host),
    patch("pyinfra.operations.server", _ops),
    patch("pyinfra.operations.systemd", _ops),
    patch("pyinfra.operations.files", _ops),
    patch("pyinfra.operations.git", _ops),
    patch("pyinfra.operations.apt", _ops),
    patch("pyinfra.operations.dnf", _ops),
    patch("pyinfra.operations.python", _ops),
    patch.object(_pyinfra_local, "include", MagicMock()),
]

for _patcher in _patchers:
    _patcher.start()


def pytest_unconfigure(config: pytest.Config) -> None:
    for patcher in _patchers:
        patcher.stop()
