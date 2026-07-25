"""Selective casting: include the runes listed in host.data._nullforge_runes."""

from pyinfra import local
from pyinfra.api.exceptions import PyinfraError
from pyinfra.context import host

from nullforge.molds.utils import ensure_features, ensure_system


def cast_selected() -> None:
    host.data.features = ensure_features(getattr(host.data, "features", None))
    host.data.system = ensure_system(getattr(host.data, "system", None))

    runes = getattr(host.data, "_nullforge_runes", None)
    if not isinstance(runes, list) or not runes or not all(isinstance(rune, str) for rune in runes):
        raise PyinfraError(
            "cast.py requires host.data._nullforge_runes (a list of absolute rune paths), "
            "invoke via `nullforge cast -r ...`."
        )

    for rune in host.loop(runes):
        local.include(rune)


cast_selected()
