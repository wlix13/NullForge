from unittest.mock import MagicMock, patch

import pyinfra.context
import pytest
from pyinfra.api.exceptions import PyinfraError

from nullforge.molds.defaults import BASE_FEATURES, BASE_SYSTEM
from nullforge.molds.utils import ensure_features, ensure_system
from nullforge.runes import rune_path


# cast_selected() runs at import time (pyinfra deploy-file convention); seed valid data
# on the conftest-patched host so the import-time call succeeds against the mocked include.
pyinfra.context.host.data._nullforge_runes = [str(rune_path("base"))]

from nullforge.foundry.cast import cast_selected  # noqa: E402


def _make_host(runes: object) -> MagicMock:
    host_mock = MagicMock()
    host_mock.data.features = ensure_features(BASE_FEATURES.model_copy())
    host_mock.data.system = ensure_system(BASE_SYSTEM.model_copy())
    host_mock.data._nullforge_runes = runes
    host_mock.loop.side_effect = lambda iterable: iter(iterable)
    return host_mock


def test_cast_selected_includes_exact_paths_in_order() -> None:
    local_mock = MagicMock()
    paths = [str(rune_path("dns")), str(rune_path("warp")), str(rune_path("base"))]

    with patch("nullforge.foundry.cast.local", local_mock), patch("nullforge.foundry.cast.host", _make_host(paths)):
        cast_selected()

    included = [call.args[0] for call in local_mock.include.call_args_list]
    assert included == paths


@pytest.mark.parametrize("invalid", [None, [], "warp", [1, 2], [str(rune_path("base")), 3]])
def test_cast_selected_rejects_invalid_rune_data(invalid: object) -> None:
    local_mock = MagicMock()

    with patch("nullforge.foundry.cast.local", local_mock), patch("nullforge.foundry.cast.host", _make_host(invalid)):
        with pytest.raises(PyinfraError):
            cast_selected()

    local_mock.include.assert_not_called()


def test_cast_selected_coerces_molds() -> None:
    local_mock = MagicMock()
    host_mock = _make_host([str(rune_path("base"))])
    host_mock.data.features = None
    host_mock.data.system = None

    with patch("nullforge.foundry.cast.local", local_mock), patch("nullforge.foundry.cast.host", host_mock):
        cast_selected()

    assert host_mock.data.features == ensure_features(None)
    assert host_mock.data.system == ensure_system(None)
