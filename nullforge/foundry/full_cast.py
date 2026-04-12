from pyinfra import local
from pyinfra.context import host

from nullforge.molds.features import iter_runes
from nullforge.molds.utils import ensure_features, ensure_system
from nullforge.runes import rune_path


def cast_full() -> None:
    host.data.features = ensure_features(getattr(host.data, "features", None))
    host.data.system = ensure_system(getattr(host.data, "system", None))

    local.include(str(rune_path("prepare")))

    local.include(str(rune_path("base")))

    for name, active in host.loop(iter_runes(host.data.features)):
        if active:
            local.include(str(rune_path(name)))


cast_full()
