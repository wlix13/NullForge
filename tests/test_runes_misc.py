import importlib

import pytest


RUNE_MODULES = [
    "nullforge.runes.base",
    "nullforge.runes.containers",
    "nullforge.runes.haproxy",
    "nullforge.runes.monitoring",
    "nullforge.runes.prepare",
    "nullforge.runes.profiles",
    "nullforge.runes.telemt",
    "nullforge.runes.tor",
    "nullforge.runes.users",
    "nullforge.runes.warp",
    "nullforge.runes.xray",
    "nullforge.runes.zerotrust",
]


@pytest.mark.parametrize("module_name", RUNE_MODULES)
def test_rune_module_exposes_deploy_entrypoint(module_name: str) -> None:
    module = importlib.import_module(module_name)
    deploy_fns = [
        name
        for name in dir(module)
        if name.startswith("deploy_")
        and callable(
            getattr(module, name),
        )
    ]
    assert deploy_fns, f"{module_name} exposes no deploy_* entrypoint"
