# Quickstart

This walkthrough casts a baseline onto one host.
You need SSH access to the target as root or a sudo-capable user.

## 1. Write an inventory

An inventory is a plain Python file that lists hosts and attaches configuration to them.
Start from the defaults and override only what differs:

```python title="inventory.py"
from nullforge.models.users import Shell
from nullforge.molds import UserMold
from nullforge.molds.defaults import BASE_FEATURES, BASE_SYSTEM
from nullforge.molds.utils import merge_features, merge_system

users = UserMold(
    manage=True,
    name="core",
    shell=Shell.ZSH,
    fetch_key_from_github="your-github-username",
)

hosts = [
    (
        "203.0.113.10",
        {
            "system": merge_system(BASE_SYSTEM, {"hostname": "node1.example.com"}),
            "features": merge_features(BASE_FEATURES, users),
        },
    ),
]
```

Replace `your-github-username` with your GitHub account before casting - its public SSH keys become the user's `authorized_keys`.

With no overrides at all, a cast still deploys the [defaults](../features/index.md): base system, network security, an admin user, Blocky DNS, and shell profiles for root.

The bundled [example inventory](https://github.com/wlix13/NullForge/blob/main/nullforge/inventories/example.py) shows a fuller setup with WARP, monitoring, and an MTProto proxy.

## 2. Preview the plan

`--dry` connects, gathers facts, and prints what would change without executing anything:

```bash
nullforge cast -i inventory.py --dry
```

## 3. Cast

```bash
nullforge cast -i inventory.py
```

pyinfra shows the proposed operations and asks for approval before executing (pass `-y` to skip the prompt).
The full cast always runs the `prepare` and `base` runes first, then every feature that is [active](../features/index.md) for the host.

Casts are idempotent - re-running converges drift and reports `no changes` for everything already in place.

## 4. Cast selectively

Deploy specific runes, in order, instead of the full set:

```bash
nullforge cast -i inventory.py -r warp -r dns
```

`-r` also takes paths to your own rune files - see [custom runes](../guides/custom-runes.md).
For fresh minimal images that lack `sudo` entirely, add [`--with-prepare`](cli.md#nullforge-cast).

## Where to go next

- [CLI reference](cli.md) - every flag, plus pyinfra pass-through.
- [Inventories](../concepts/inventories.md) - layering and merge semantics.
- [Feature reference](../features/index.md) - what each feature deploys and its configuration.
