# Runes

A rune is one deployable concern: a single pyinfra operation set that is idempotent and self-contained.
Built-in runes live in `nullforge/runes/`, one file each.

```bash
nullforge runes   # list built-in runes with summaries
```

## Execution

Runes are executed, not imported.
The foundry (or the selective `cast.py`) pulls each one in with pyinfra's `local.include`, so the module-level code runs at deploy time with `host` bound to the current target.
Every rune file defines a `deploy_*()` function and calls it at the bottom.

A typical rune:

```python
"""Tor proxy deployment module."""

from pyinfra.context import host
from pyinfra.operations import files, systemd

from nullforge.molds import FeaturesMold, TorMold
from nullforge.smithy.packages import get_pm
from nullforge.templates import get_template_path


def deploy_tor() -> None:
    features: FeaturesMold = host.data.features
    tor_opts: TorMold = features.tor

    get_pm().install(name="Install Tor package", packages=["tor"], _sudo=True)

    config = files.template(
        name="Deploy Tor proxy configuration",
        src=get_template_path("tor/torrc.j2"),
        dest="/etc/tor/torrc",
        SOCKS_PORT=tor_opts.socks_port,
        DNS_PORT=tor_opts.dns_port,
        _sudo=True,
    )

    systemd.service(service="tor", restarted=True, _sudo=True, _if=config.did_change)
    systemd.service(service="tor", running=True, enabled=True, _sudo=True)


deploy_tor()
```

The pattern to note: configuration comes from `host.data`, distro differences go through the smithy (`get_pm()`), and service restarts are guarded by [change detection](../contributing/conventions.md#change-detection).

## Dispatch

The full cast derives its rune list from `FeaturesMold` itself:

1. [`prepare` and `base`](../features/base.md) always run first.
2. Every feature field is visited in declaration order; its rune is included when the sub-mold's `is_active` is true.

The rune name defaults to the field name (`warp` -> `runes/warp.py`).
A sub-mold can override it with `_feature_rune = "other-name"`, or opt out of dispatch with `_feature_rune = None`.

The resulting deploy order is the [feature table](../features/index.md) top to bottom, filtered to active features.

## Independence

No rune imports another rune.
Cross-feature coordination happens through configuration instead: a rune may *read* another feature's mold (Telemt reads `features.warp` to set up policy routing) but never calls into another rune's code.

This keeps selective casts honest - `nullforge cast -r telemt` behaves the same whether or not the WARP rune ran in the same invocation.

## Custom runes

`-r` accepts paths as well as built-in names - the [custom runes guide](../guides/custom-runes.md) covers writing your own.
