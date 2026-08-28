"""Features controller model."""

from collections.abc import Iterator

from pydantic import Field

from .base_mold import BaseMold
from .containers import ContainersMold
from .dns import DnsMold
from .haproxy import HaproxyMold
from .monitoring import MonitoringMold
from .netsec import NetSecMold
from .profiles import ProfilesMold
from .telemt import TelemtMold
from .tor import TorMold
from .user import UserMold
from .warp import WarpMold
from .xray import XrayCoreMold
from .zerotrust import ZeroTrustTunnelMold


class FeaturesMold(BaseMold):
    """Defines all supported molds and order of deployment."""

    warp: WarpMold = Field(default_factory=WarpMold)
    dns: DnsMold = Field(default_factory=DnsMold)
    users: UserMold = Field(default_factory=UserMold)
    netsec: NetSecMold = Field(default_factory=NetSecMold)
    profiles: ProfilesMold = Field(default_factory=ProfilesMold)
    zerotrust: ZeroTrustTunnelMold = Field(default_factory=ZeroTrustTunnelMold)
    containers: ContainersMold = Field(default_factory=ContainersMold)
    monitoring: MonitoringMold = Field(default_factory=MonitoringMold)
    haproxy: HaproxyMold = Field(default_factory=HaproxyMold)
    xray: XrayCoreMold = Field(default_factory=XrayCoreMold)
    tor: TorMold = Field(default_factory=TorMold)
    telemt: TelemtMold = Field(default_factory=TelemtMold)


FEATURE_MOLD_MAPPING: dict[str, type[BaseMold]] = {}
"""Derived after class definition. Adding a feature field automatically updates these."""


def _build_mold_map() -> None:
    global FEATURE_MOLD_MAPPING
    mapping: dict[str, type[BaseMold]] = {}
    for name, finfo in FeaturesMold.model_fields.items():
        ann = finfo.annotation
        if isinstance(ann, type) and issubclass(ann, BaseMold) and ann is not BaseMold:
            mapping[name] = ann
    FEATURE_MOLD_MAPPING = mapping


_build_mold_map()

ALLOWED_FEATURES_LAYERS: tuple[type[BaseMold], ...] = tuple(FEATURE_MOLD_MAPPING.values())
"""Allowed molds for the FeaturesMold."""


def iter_runes(features: FeaturesMold) -> Iterator[tuple[str, bool]]:
    """Yield every dispatchable (rune name, active) pair, in a stable order.

    Rune name defaults to attribute name under FeaturesMold (e.g. "warp" -> "warp").
    Sub-mold classes may set `_feature_rune: ClassVar[str | None]`:
      - str value overrides the rune stem
      - None value opts the feature out of automatic dispatch
    """

    yielded: set[str] = set()

    for attr, mold_cls in FEATURE_MOLD_MAPPING.items():
        rune_name = getattr(mold_cls, "_feature_rune", attr)
        if rune_name is None or rune_name in yielded:
            continue
        yielded.add(rune_name)
        yield rune_name, getattr(features, attr).is_active
