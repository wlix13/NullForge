"""Pyinfra launcher that labels deploys by rune stem instead of full file path.

Equivalent to `python -m pyinfra`, but first installs monkeypatches so operation names and `Loading:`/`Ready:` header
lines show rune stem (e.g. `base`) instead of absolute path.
"""

from __future__ import annotations

import logging
from functools import wraps
from os import path
from typing import overload


LOG = logging.getLogger(__name__)

_patched: set[str] = set()
"""Patch keys already installed, so `apply_patches()` is idempotent within a process."""


@overload
def _stem(name: str) -> str: ...
@overload
def _stem(name: None) -> None: ...
def _stem(name: str | None) -> str | None:
    """Reduce `*.py` file path to bare stem."""

    if name and name.endswith(".py"):
        return path.splitext(path.basename(name))[0]
    return name


def _patch_operation_names() -> None:
    """Label deploy contexts by rune stem so operation names read `base | <op>`."""

    if "operation_names" in _patched:
        return

    from pyinfra.api import host as host_module

    original = host_module.Host.deploy

    @wraps(original)
    def deploy(self, name: str, kwargs, data, in_deploy=True):
        return original(self, _stem(name), kwargs, data, in_deploy)

    host_module.Host.deploy = deploy  # ty:ignore[invalid-assignment]
    _patched.add("operation_names")


def _patch_ready_message() -> None:
    """Show deploy/rune stem in `Ready:` lines."""

    if "ready_message" in _patched:
        return

    from pyinfra_cli import util as util_module

    original = util_module._parallel_load_hosts

    @wraps(original)
    def _parallel_load_hosts(state, callback, name: str):
        return original(state, callback, _stem(name))

    util_module._parallel_load_hosts = _parallel_load_hosts  # ty:ignore[invalid-assignment]
    _patched.add("ready_message")


def _patch_loading_message() -> None:
    """Show deploy stem in `Loading:` line."""

    if "loading_message" in _patched:
        return

    from pyinfra_cli import cli as cli_module

    def _prepare_deploy_operations(state, config, operations):
        for i, filename in enumerate(operations):
            config.lock_current_state()
            cli_module.logger.info(f"Loading: {cli_module.click.style(_stem(str(filename)), bold=True)}")
            state.current_op_file_number = i
            cli_module.load_deploy_file(state, filename)
            config.reset_locked_state()
        return state, config, operations

    cli_module._prepare_deploy_operations = _prepare_deploy_operations  # ty:ignore[invalid-assignment]
    _patched.add("loading_message")


def apply_patches() -> None:
    """Install display patches."""

    for patch in (_patch_operation_names, _patch_ready_message, _patch_loading_message):
        try:
            patch()
        except Exception:
            LOG.debug(f"Could not apply pyinfra display patch {patch.__name__}", exc_info=True)


def main() -> None:
    """Install display patches, then hand off to Pyinfra's entrypoint."""

    apply_patches()

    from pyinfra_cli.main import main as pyinfra_main

    pyinfra_main()


if __name__ == "__main__":
    main()
