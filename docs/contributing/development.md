# Development

Tasks, tests, commit conventions and the pull request flow are in [CONTRIBUTING.md](https://github.com/wlix13/NullForge/blob/main/.github/CONTRIBUTING.md); this page covers setup and the documentation site.

## Setup

Only [uv](https://docs.astral.sh/uv/) is supported:

```bash
git clone https://github.com/wlix13/NullForge
cd NullForge
uv sync
uv run prek install   # git hooks via prek
```

## Documentation

The site is built with [zensical](https://zensical.org) from `docs/` and `zensical.toml`:

```bash
uv run poe docs:dev   # http://localhost:8000, live reload
uv run poe docs       # strict build into site/
```

All docs are Markdown, linted by markdownlint (`.markdownlint-cli2.jsonc`; MD013 is off - prose is written one sentence per line).
CI builds the site strictly on docs PRs and deploys `main` to GitHub Pages.
