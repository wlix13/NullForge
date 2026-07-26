# Development

Issue and PR flow, commit conventions, and expectations are in [CONTRIBUTING.md](https://github.com/wlix13/NullForge/blob/main/.github/CONTRIBUTING.md); this page covers the local toolchain.

## Setup

Only [uv](https://docs.astral.sh/uv/) is supported:

```bash
git clone https://github.com/wlix13/NullForge
cd NullForge
uv sync
uv run prek install   # git hooks via prek
```

## Tasks

Everything routine is a [poe](https://poethepoet.natn.io/) task:

| Task | What it runs |
| --- | --- |
| `poe format` / `poe check-format` | `ruff format` (fix / check) |
| `poe lint` | `ruff check` |
| `poe typecheck` | `ty check` |
| `poe lint-imports` | import-linter [layer contracts](../concepts/architecture.md#layer-contracts) |
| `poe deptry` | dependency hygiene |
| `poe lint-md` | markdownlint over all Markdown (via prek) |
| `poe check` | check-format + lint + lint-md + typecheck + lint-imports + deptry |
| `poe tests` | pytest with coverage |
| `poe docs` | strict site build (what docs CI runs) |
| `poe docs:dev` | serve this site locally with live reload |

`uv run prek run --all-files` runs the full hook set (formatting, ruff, pyproject-fmt, markdownlint, lockfile freshness).

## Tests

```bash
uv run --group tests pytest
```

`tests/conftest.py` patches the pyinfra context so rune and operation calls are no-ops - molds, smithy helpers, runes, and templates unit-test without a real target.
End-to-end correctness is still validated by deploying to a real host.

The suite also enforces the [conventions](conventions.md): operation-emitting loops must go through `host.loop`, and import contracts reject cross-layer imports.

## Documentation

The site is built with [zensical](https://zensical.org) from `docs/` and `zensical.toml`:

```bash
poe docs:dev   # http://localhost:8000, live reload
poe docs       # strict build into site/
```

All docs are Markdown, linted by markdownlint (`.markdownlint-cli2.jsonc`; MD013 is off - prose is written one sentence per line).
CI builds the site strictly on docs PRs and deploys `main` to GitHub Pages.

## CI

| Workflow | Trigger | What it does |
| --- | --- | --- |
| 🔍 Check code quality | push/PR to `main` | ruff, ty, import contracts, deptry, prek hooks (incl. markdownlint) |
| 🧪 Tests | push/PR to `main` | pytest + package build check |
| 📚 Docs build check | PR touching docs | strict zensical build |
| 📚 Deploy documentation | push to `main` touching docs | build + publish to GitHub Pages |
| release-please | push to `main` | release PR / GitHub releases from conventional commits |

Commits follow [Conventional Commits](https://www.conventionalcommits.org) - release-please derives versions and the changelog from them.
