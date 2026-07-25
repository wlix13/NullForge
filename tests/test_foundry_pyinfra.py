from collections.abc import Iterator

import pytest
from pyinfra.api import host as host_module
from pyinfra_cli import cli as cli_module
from pyinfra_cli import util as util_module

from nullforge.foundry import _pyinfra


class TestStem:
    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            ("/home/x/runes/base.py", "base"),
            ("full_cast.py", "full_cast"),
            ("../runes/dns.py", "dns"),
            ("@local", "@local"),
            ("", ""),
            (None, None),
        ],
    )
    def test_stem(self, value: str | None, expected: str | None) -> None:
        assert _pyinfra._stem(value) == expected


@pytest.fixture
def restore_pyinfra() -> Iterator[None]:
    """Snapshot Pyinfra functions patches mutate and restore them."""

    saved_deploy = host_module.Host.deploy
    saved_ready = util_module._parallel_load_hosts
    saved_loading = cli_module._prepare_deploy_operations
    saved_patched = _pyinfra._patched.copy()
    try:
        yield
    finally:
        host_module.Host.deploy = saved_deploy
        util_module._parallel_load_hosts = saved_ready
        cli_module._prepare_deploy_operations = saved_loading
        _pyinfra._patched.clear()
        _pyinfra._patched.update(saved_patched)


class TestApplyPatches:
    def test_wraps_all_three_functions(self, restore_pyinfra: None) -> None:

        before = (
            host_module.Host.deploy,
            util_module._parallel_load_hosts,
            cli_module._prepare_deploy_operations,
        )
        _pyinfra.apply_patches()
        after = (
            host_module.Host.deploy,
            util_module._parallel_load_hosts,
            cli_module._prepare_deploy_operations,
        )

        assert all(b is not a for b, a in zip(before, after)), "all three functions must be wrapped"

    def test_is_idempotent(self, restore_pyinfra: None) -> None:

        _pyinfra.apply_patches()
        first = host_module.Host.deploy
        _pyinfra.apply_patches()

        assert host_module.Host.deploy is first, "second apply_patches must not re-wrap"


class TestLoadingMessage:
    def test_shortens_log_but_loads_real_path(self, restore_pyinfra: None, monkeypatch: pytest.MonkeyPatch) -> None:

        logged: list[str] = []
        loaded: list[str] = []

        _pyinfra._patch_loading_message()
        monkeypatch.setattr(cli_module.logger, "info", lambda msg: logged.append(msg))
        monkeypatch.setattr(cli_module, "load_deploy_file", lambda state, filename: loaded.append(filename))

        class Config:
            def lock_current_state(self) -> None: ...
            def reset_locked_state(self) -> None: ...

        class State: ...

        cli_module._prepare_deploy_operations(
            State(),
            Config(),
            ["/home/x/foundry/full_cast.py"],
        )

        assert any("full_cast" in line and "full_cast.py" not in line for line in logged), logged
        assert loaded == ["/home/x/foundry/full_cast.py"], "the real path must still be loaded"
