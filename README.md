# NullForge

Forge the server's baseline from null — an infrastructure-as-code framework built on [pyinfra](https://pyinfra.com), themed around a blacksmith's forge: **inventories** define hosts, **molds** shape the configuration, **runes** are idempotent operation sets, the **foundry** casts them onto targets, and the **smithy** holds cross-distro helpers.

> [!WARNING]
> **NullForge is in active development.** Until the `v1.0.0` release, the CLI, mold schemas and deploy behaviour may change at any time — breaking changes can land in **any** release, including patch versions. Pin an exact version (e.g. `nullforge==0.1.0`) and check the [release notes](https://github.com/wlix13/NullForge/releases) before upgrading.

## Install

```bash
# Latest release from PyPI — puts `nullforge` on PATH
uv tool install nullforge
```

From a source checkout instead, when you want the Python API (`nullforge.molds`, `nullforge.smithy`, ...) or to hack on NullForge itself:

```bash
uv sync
```

Every command below then runs as `uv run nullforge ...`.

## CLI

```bash
# Full cast (all enabled features from the inventory)
nullforge cast -i nullforge/inventories/example.py

# Cast specific runes, in order (built-in names or paths to custom rune files)
nullforge cast -i nullforge/inventories/example.py -r warp -r dns
nullforge cast -i nullforge/inventories/example.py -r ./my_rune.py

# Fresh host without sudo: run the prepare rune as a separate first deploy
nullforge cast -i nullforge/inventories/example.py -r base --with-prepare

# Connection flags are proxied to pyinfra; unknown options pass through verbatim
nullforge cast -i nullforge/inventories/example.py -r dns --ssh-user root --ssh-port 2222 --dry -v

# List built-in runes
nullforge runes

# Shell completion (bash, zsh, fish, powershell) — print or install
nullforge completion powershell --install
```

Custom rune files are plain pyinfra deploy modules and can use the full NullForge API, since they run in the same environment.

Note for PowerShell users: quote `@local`-style host specs (`-i "@local"`) — unquoted `@name` is PowerShell splatting syntax and is swallowed by the shell.

## Contributing

See [CONTRIBUTING.md](.github/CONTRIBUTING.md) for the full setup, commit conventions and pull request flow.
