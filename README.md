# NullForge

Forge the server's baseline from null — an infrastructure-as-code framework built on [pyinfra](https://pyinfra.com), themed around a blacksmith's forge: **inventories** define hosts, **molds** shape the configuration, **runes** are idempotent operation sets, the **foundry** casts them onto targets, and the **smithy** holds cross-distro helpers.

> [!WARNING]
> **NullForge is in active development.** Until the `v1.0.0` release, the mold schemas, runes and deploy behaviour may change at any time — breaking changes can land in **any** release, including patch versions. Pin an exact version (e.g. `nullforge==0.1.0`) and check the [release notes](https://github.com/wlix13/NullForge/releases) before upgrading.

## Install

```bash
uv sync
```

## Deploy

```bash
# Cast the full baseline (all enabled features from the inventory)
uv run pyinfra nullforge/inventories/example.py nullforge/foundry/full_cast.py
```

## Contributing

See [CONTRIBUTING.md](.github/CONTRIBUTING.md) for the full setup, commit conventions and pull request flow.
