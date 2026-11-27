from unittest.mock import MagicMock, patch

# conftest patches pyinfra.local so foundry can be imported without CLI mode error.
# We import cast_full at module level so the module is in sys.modules.
from nullforge.foundry.full_cast import cast_full
from nullforge.molds.defaults import BASE_FEATURES, BASE_SYSTEM
from nullforge.molds.utils import ensure_features, ensure_system


def test_cast_full_always_includes_base_runes() -> None:
    local_mock = MagicMock()
    host_mock = MagicMock()
    host_mock.loop.side_effect = lambda iterable: iter(iterable)
    host_mock.data.features = ensure_features(BASE_FEATURES.model_copy())
    host_mock.data.system = ensure_system(BASE_SYSTEM.model_copy())

    with patch("nullforge.foundry.full_cast.local", local_mock):
        with patch("nullforge.foundry.full_cast.host", host_mock):
            cast_full()

    included = [c.args[0] for c in local_mock.include.call_args_list]
    assert any("prepare.py" in p for p in included)
    assert any("base.py" in p for p in included)
    assert any("netsec.py" in p for p in included)


def test_cast_full_skips_disabled_features() -> None:
    local_mock = MagicMock()
    host_mock = MagicMock()
    host_mock.loop.side_effect = lambda iterable: iter(iterable)
    host_mock.data.features = ensure_features(BASE_FEATURES.model_copy())
    host_mock.data.system = ensure_system(BASE_SYSTEM.model_copy())

    with patch("nullforge.foundry.full_cast.local", local_mock):
        with patch("nullforge.foundry.full_cast.host", host_mock):
            cast_full()

    included = [c.args[0] for c in local_mock.include.call_args_list]
    assert not any("warp.py" in p for p in included)
    assert not any("zerotrust.py" in p for p in included)
    assert not any("haproxy.py" in p for p in included)
    assert not any("containers.py" in p for p in included)
    assert not any("tor.py" in p for p in included)
    assert not any("xray.py" in p for p in included)
    assert any("dns.py" in p for p in included)
    assert any("users.py" in p for p in included)
    assert any("netsec.py" in p for p in included)
    assert any("profiles.py" in p for p in included)

    host_mock.data.features = ensure_features({"netsec": {"install": False}})
    local_mock.reset_mock()
    with patch("nullforge.foundry.full_cast.local", local_mock):
        with patch("nullforge.foundry.full_cast.host", host_mock):
            cast_full()
    disabled = [c.args[0] for c in local_mock.include.call_args_list]
    assert not any("netsec.py" in p for p in disabled)
