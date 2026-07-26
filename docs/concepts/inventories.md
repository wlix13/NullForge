# Inventories

An inventory is a standard [pyinfra inventory](https://docs.pyinfra.com/en/3.x/inventory-data.html): a Python file with a `hosts` list.
Each host is either a bare address or an `(address, data)` tuple.
NullForge reads two data keys - `system` and `features` - plus an optional `versions` map for [pin overrides](../guides/version-pinning.md).

```python
from nullforge.molds.defaults import BASE_FEATURES, BASE_SYSTEM
from nullforge.molds.utils import merge_features, merge_system

hosts = [
    (
        "203.0.113.10",
        {
            "system": merge_system(BASE_SYSTEM, {"hostname": "node1.example.com"}),
            "features": merge_features(BASE_FEATURES, ...),
        },
    ),
]
```

## Defaults and layering

`BASE_SYSTEM` and `BASE_FEATURES` (from `nullforge.molds.defaults`) are plain default-constructed molds.
`merge_system` / `merge_features` (from `nullforge.molds.utils`) start from a base and deep-merge each layer in order - later layers win.

A features layer can be any of:

| Layer type | Example |
| --- | --- |
| Full `FeaturesMold` | another host's merged result |
| Any feature sub-mold | `WarpMold(install=True)` - merged under its own key |
| `dict` fragment | `{"warp": {"install": True}}` (sub-molds allowed as values) |
| `None` | skipped; useful for conditional layers |

```python
from nullforge.molds import DnsMold, UserMold, WarpMold

common = (
    UserMold(manage=True, name="core"),
    WarpMold(install=True),
)

features = merge_features(BASE_FEATURES, *common, {"dns": {"ecs": True}})
```

The set of allowed sub-mold types is derived from `FeaturesMold.model_fields`, so a new feature is mergeable without touching the merge logic.

!!! warning "Deep-merge is per-key"

    Dictionaries merge recursively, but any non-dict value - including lists - replaces the previous value outright.
    A layer that sets `netsec.firewall_rules` replaces the whole rule list; extend `BASE_FEATURES.netsec.firewall_rules` in Python if you want "default rules plus mine".

Because inventories are Python, you can factor shared preset tuples, per-environment modules, or host loops however you like - the only contract is the final `hosts` list.

## Validation and coercion

The foundry coerces whatever the inventory provided - `None`, a `dict`, or a mold instance - into validated `SystemMold` / `FeaturesMold` objects before any rune runs (`ensure_system` / `ensure_features`).
Missing keys fall back to mold defaults; unknown keys are rejected because every mold forbids extra fields.
A typo like `{"warp": {"instal": True}}` fails the cast at validation time, before anything touches a host.

## Scaling to a fleet

Inventories are Python, so fleet structure is ordinary code.
A pattern that works well in practice: per-zone feature presets, a YAML host registry, and a small builder that turns them into pyinfra groups.

Shared mold instances compose into one `FeaturesMold` per zone:

```python title="inventory/zones.py"
from nullforge.models.netsec import SshHostKeyType
from nullforge.molds import ContainersMold, FeaturesMold, FirewallRule, HaproxyMold, NetSecMold, SshMold, UserMold
from nullforge.molds.defaults import BASE_FEATURES
from nullforge.molds.utils import merge_features

netsec = NetSecMold(
    firewall_rules=[
        FirewallRule(port=443, comment="HTTPS"),
        FirewallRule(port=22, proto="tcp", from_ip="203.0.113.7", comment="Admin SSH"),
    ],
    ssh=SshMold(host_keys=[SshHostKeyType.ED25519]),
)

users = UserMold(name="ops", fetch_key_from_github="your-github-username")

ZONE_FEATURES: dict[str, FeaturesMold] = {
    "web": merge_features(BASE_FEATURES, netsec, users, HaproxyMold(install=True)),
    "workers": merge_features(BASE_FEATURES, netsec, users, ContainersMold(install=True)),
}
```

Host membership lives in data, not code - one YAML entry per host, with an optional `overrides` fragment deep-merged onto the zone preset:

```yaml title="inventory/hosts.yaml"
web:
  - address: 203.0.113.10
    hostname: web1.example.com
  - address: 203.0.113.11
    hostname: web2.example.com
    overrides:
      netsec:
        firewall: false
workers:
  - address: 203.0.113.20
    hostname: worker1.example.com
```

The builder exposes one module-level list per zone - pyinfra treats each as a named group, so `--limit web` targets a whole zone:

```python title="inventory/main.py"
from pathlib import Path

import yaml

from nullforge.molds.defaults import BASE_SYSTEM
from nullforge.molds.utils import merge_features, merge_system

from inventory.zones import ZONE_FEATURES

DATA: dict = yaml.safe_load((Path(__file__).parent / "hosts.yaml").read_text()) or {}


def _build(zone: str) -> list:
    rows = []
    for entry in DATA.get(zone, []):
        rows.append(
            (
                entry["address"],
                {
                    "zone": zone,
                    "system": merge_system(BASE_SYSTEM, {"hostname": entry["hostname"]}),
                    "features": merge_features(ZONE_FEATURES[zone], entry.get("overrides")),
                },
            )
        )
    return rows


for zone in ZONE_FEATURES:
    globals()[zone] = _build(zone)
```

```bash
nullforge cast -i inventory/main.py --limit web --dry
```

Details worth stealing:

- `entry.get("overrides")` is either a dict fragment or `None` - both are valid `merge_features` layers, so per-host overrides cost one line and still go through mold validation.
- Extra data keys (like `zone` above) ride along on `host.data` untouched; [custom runes](../guides/custom-runes.md) can branch on them.
- Adding a host is a YAML edit, reviewable in a PR and scriptable from CI.

This is the pattern behind the deploy repo of the **Conglomerate** proxy fleet: zone presets over NullForge molds, a YAML host registry edited from CI workflows, and per-zone `--limit` casts.

## Secrets in inventories

Inventories are code; secrets in them (tunnel tokens, proxy user secrets) end up on disk.
Keep real inventories out of public repos, or load secrets from the environment.

Mold fields marked sensitive (user password, Zero Trust token, Nezha secrets, Telemt users) are redacted as `***` in pyinfra's `--debug-inventory` output, so inspecting a plan does not leak them.

## Debugging

```bash
nullforge cast -i inventory.py --debug-inventory   # dump merged host data (pass-through to pyinfra)
```
