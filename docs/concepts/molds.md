# Molds

Molds are Pydantic models that shape and validate every piece of NullForge configuration.
If a value reaches a rune, it went through a mold first.

## BaseMold

Every mold extends `BaseMold` (`nullforge/molds/base_mold.py`), which sets the shared behaviour:

- **`extra="forbid"`** - unknown keys are validation errors, so typos fail the cast instead of silently deploying defaults.
- **`is_active`** - the activation protocol used for [rune dispatch](runes.md#dispatch); each feature sub-mold implements it.
- **`to_json()`** - JSON-mode serialization for pyinfra's `--debug-inventory`, with `_sensitive_fields` values redacted as `***` (recursively, through nested molds, lists and dicts).

## The top-level molds

Two molds cover a host:

- **`SystemMold`** - base system state: packages, locales, timezone, hostname, swap, IPv6.
  Consumed by the always-on [base rune](../features/base.md).
- **`FeaturesMold`** - one field per feature, each a sub-mold with its own defaults:

```python
class FeaturesMold(BaseMold):
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
```

Field order is deploy order.
Everything else is derived from these fields - the allowed [merge layers](inventories.md), the feature-to-mold mapping, and rune dispatch - so adding a feature means adding a field, not editing plumbing.

## Activation

Every feature sub-mold implements `is_active`.
Most simply return `self.install`; the exceptions encode their own semantics:

- `DnsMold` - active while `mode != "none"`.
- `UserMold` - active while `manage` is true.
- `ProfilesMold` - active while `for_root` or `for_user` is true.

A sub-mold may also rename its rune or opt out of automatic dispatch - see [dispatch](runes.md#dispatch).

## Validation beyond types

Molds validate coherence, not just shapes - a bad combination fails at plan time with a readable error, never mid-deploy.
Each [feature page](../features/index.md) documents its own validators.

## Models vs molds

Domain types and constants - `DnsMode`, `Shell`, `WarpEngineType`, `SwapType`, ... - live in `nullforge.models.<domain>` and are imported from there directly:

```python
from nullforge.models.dns import DnsMode
from nullforge.molds import DnsMold

dns = DnsMold(mode=DnsMode.DOT_RESOLVED)
```

`nullforge.molds` exports only the molds.
The split is enforced by an import contract: models import nothing from the rest of the package.
