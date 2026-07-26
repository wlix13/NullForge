# NullForge

[![PyPI](https://img.shields.io/pypi/v/nullforge?logo=pypi&logoColor=white)](https://pypi.org/project/nullforge/)
![Python](https://img.shields.io/badge/python-3.13-blue?logo=python&logoColor=white)
![Build](https://img.shields.io/github/actions/workflow/status/wlix13/NullForge/ci-tests.yaml?label=build&logo=github)
![Lint](https://img.shields.io/github/actions/workflow/status/wlix13/NullForge/ci-code-quality.yaml?label=lint&logo=github)
![License](https://img.shields.io/badge/license-MIT-green)
![uv](https://img.shields.io/badge/package%20manager-uv-blueviolet?logo=astral)
![Ruff](https://img.shields.io/badge/linter-ruff-orange?logo=ruff)
[![Docs](https://img.shields.io/badge/docs-GitHub%20Pages-0075ca?logo=materialformkdocs&logoColor=white)](https://wlix13.github.io/NullForge/)

Forge the server's baseline from null - an infrastructure-as-code framework built on [pyinfra](https://pyinfra.com), themed around a blacksmith's forge: **inventories** define hosts, **molds** shape the configuration, **runes** are idempotent operation sets, the **foundry** casts them onto targets, and the **smithy** holds cross-distro helpers.

> [!WARNING]
> **NullForge is in active development.** Until the `v1.0.0` release, the CLI, mold schemas and deploy behaviour may change at any time - breaking changes can land in **any** release, including patch versions. Pin an exact version (e.g. `nullforge==0.2.0`) and check the [release notes](https://github.com/wlix13/NullForge/releases) before upgrading.

## Install

```bash
uv tool install nullforge
```

## Documentation

Everything else - getting started, concepts, the full feature reference, and guides - lives at **[wlix13.github.io/NullForge](https://wlix13.github.io/NullForge/)**.

## Contributing

See [CONTRIBUTING.md](.github/CONTRIBUTING.md) for the full setup, commit conventions and pull request flow.
