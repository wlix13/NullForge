# Installation

NullForge runs on a control node (your machine) and provisions targets over SSH via pyinfra.
Nothing is installed on the targets beforehand - a root or sudo-capable SSH login is enough.

## Requirements

- **Control node** - Python 3.13 and [uv](https://docs.astral.sh/uv/).
- **Targets** - Debian or Ubuntu (primary), RHEL-family (Rocky, Alma, CentOS, Fedora - supported where noted per feature), reachable over SSH.

## As a CLI tool

The released package puts `nullforge` on your `PATH`:

```bash
uv tool install nullforge
```

!!! note "Pin the version"

    NullForge is pre-1.0 - breaking changes can land in any release.
    Prefer `uv tool install "nullforge==0.2.0"` and upgrade deliberately.

## From a source checkout

Use a checkout when you want the Python API (`nullforge.molds`, `nullforge.smithy`, ...) - for example to write [custom runes](../guides/custom-runes.md) or typed inventories - or to hack on NullForge itself:

```bash
git clone https://github.com/wlix13/NullForge
cd NullForge
uv sync
```

Every command then runs as `uv run nullforge ...`.

Only `uv` is supported for source installs; `pip`/`conda` environments are not tested and dependency versions are not guaranteed.

Shell completion for bash, zsh, fish, and PowerShell is available via [`nullforge completion`](cli.md#nullforge-completion).

Next: the [quickstart](quickstart.md) walks through a first deploy.
