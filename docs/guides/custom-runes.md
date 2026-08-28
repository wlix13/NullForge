# Custom runes

A custom rune is a plain pyinfra deploy module run with `-r`:

```bash
nullforge cast -i inventory.py -r ./runes/my_rune.py
nullforge cast -i inventory.py -r base -r ./runes/my_rune.py   # mix with built-ins, order preserved
```

Custom runes run in the same environment as built-in ones: `host.data.system` and `host.data.features` arrive as validated molds, and the full NullForge API - smithy helpers, templates, models - is importable.
Keep them in your deployment repo next to the inventory.

## Skeleton

```python title="runes/my_rune.py"
"""One-line summary of what this rune deploys."""

from pyinfra.context import host
from pyinfra.operations import files, systemd

from nullforge.molds import FeaturesMold
from nullforge.smithy.packages import get_pm


def deploy_my_rune() -> None:
    features: FeaturesMold = host.data.features

    get_pm().install(name="Install my package", packages=["mypackage"], _sudo=True)

    config = files.put(
        name="Deploy my config",
        src="files/my.conf",
        dest="/etc/my/my.conf",
        mode="0644",
        _sudo=True,
    )

    systemd.service(service="my", restarted=True, _sudo=True, _if=config.did_change)
    systemd.service(service="my", running=True, enabled=True, _sudo=True)


deploy_my_rune()
```

The file must call its deploy function at module level - see [how runes execute](../concepts/runes.md#execution).

## Reacting to features and host data

Everything the inventory attached is on `host.data`.
Branch on other features' molds to compose with them, and on your own extra keys for role logic:

```python
features: FeaturesMold = host.data.features

if features.haproxy.install:
    ...  # grant an automation user access to the haproxy config

if getattr(host.data, "zone", None) == "web":
    ...  # zone-specific provisioning
```

The deploy repo of the **Conglomerate** proxy fleet uses this shape for a repo-local automation rune: it provisions a CI user, then derives that user's sudoers entries and ACL grants from whichever features are active on each host.

## Useful smithy helpers

| Helper | Use |
| --- | --- |
| `smithy.packages.get_pm()` | Distro-mapped package install/update/upgrade (apt/dnf) |
| `smithy.install.install_release_binary()` | Download -> sha256-verify -> extract -> install a release binary |
| `smithy.http.curl_args(url)` | Hardened `extra_curl_args` for `files.download`, falling back to [WARP](../features/warp.md#downloads-through-warp) when the direct route is filtered |
| `smithy.versions.is_pinned_version_installed()` | Skip installs already at the [pinned version](version-pinning.md) |
| `smithy.service.ensure_service_user()` | Dedicated system user + group for a service |
| `smithy.admin.ensure_acl_access()` | Grant a user ACL access to a directory tree |
| `smithy.network.has_ipv6()` | IPv6 connectivity fact |
| `templates.get_template_path()` / `render_template()` | Jinja2 templates (your own paths work too) |

## Rules that keep casts stable

Custom runes follow the same [conventions](../contributing/conventions.md) as built-ins - `host.loop` for operation-emitting loops, `OperationMeta` change-detection guards, and fact- or [pin](version-pinning.md)-guarded installs.
