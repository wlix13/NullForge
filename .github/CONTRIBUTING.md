# Contribution Guidelines

First of all, thank you for your interest in the project.

Regardless of whether you are thinking about creating an issue or opening a pull request, I truly appreciate the help.
Without communication, I cannot know what the community wants, what they use or how they use it.
Pull requests and issues are exactly what gives me the visibility I need, so thank you.

## Getting started

While following the exact process is neither mandatory nor enforced, it is recommended to try following it as it may help avoid wasted efforts.

### Creating an issue

Whether you have a **question**, found a **bug**, would like to see a **new feature** added or anything along those lines, creating an issue is
going to be the first step. The issue templates will help guide you, but simply creating an issue with the reason for the creation
of said issue is perfectly fine.

Furthermore, if you don't want to fix the problem or implement the feature yourself, that's completely fine.
Creating an issue alone will give both the maintainers as well as the other members of the community visibility on said issue,
which is a lot more likely to get the issue resolved than if the problem/request was left untold.

### Solving an issue

Looking to contribute? Awesome! Look through the open issues in the repository, preferably those that are already labelled.

If you found one that interests you, try to make sure nobody's already working on it.
Adding a comment to the issue asking the maintainer if you can tackle it is a perfectly acceptable way of doing that!

If there's no issue yet for what you want to solve, start by [Creating an issue](#creating-an-issue), specify
you'd like to take a shot at solving it, and finally, wait for the maintainer to comment on the issue.

You don't _have_ to wait for the maintainer to comment on the issue before starting to work on it if you're sure that there's no other
similar existing issues, open or closed, but if the maintainer has commented, it means the maintainer has, based on the comment itself,
acknowledged the issue.

## Development Setup

### Package Management

This project **only** supports the `uv` installation method. Other tools, such as `conda`
or `pip`, don't provide any guarantees that they will install the correct
dependency versions. You will almost certainly have _random bugs, error messages,_, and other problems if you don't use `uv`.
Please _do not report any issues_ if you use non-standard installations, since almost all such issues are invalid.

Furthermore, `uv` is [up to 115x faster](https://github.com/astral-sh/uv/blob/main/BENCHMARKS.md)
than `pip`, which is another _great_ reason to embrace the new industry-standard
for Python project management.

**Quick & Easy Installation Method:**

There are many convenient ways to install the uv command on your computer. Please check the link below to see all options.

[Installation Guide](https://docs.astral.sh/uv/getting-started/installation/)

Alternatively, if you want a very quick and easy method, you can install it as follows:

```bash
pip install -U uv
```

### Pre-commit Hooks (via prek)

This project uses pre-commit hooks to ensure code quality and consistency. Before making any commits, please install and set up prek:

```bash
# Install prek (if not already installed)
uv tool install prek
# or use with uv run (as dev environment already has it covered)
uv run prek

# Install the pre-commit hooks
prek install
```

The pre-commit hooks will automatically run on each commit to check for:

- Code formatting
- Linting issues
- Other quality checks

If any hooks fail, please fix the issues before committing. You can manually run all hooks with:

```bash
prek run --all-files
```

### Tasks (via poe)

Every routine check, build and test step is a [poe](https://poethepoet.natn.io/) task, and CI runs the same tasks you do.
Tasks run through poe's `uv` executor, so they resolve their own environment - no `uv run --group ...` prefix needed.
The bare name is the variant CI runs; a colon suffix selects a mode (`:fix` for auto-fix, `:dev` for the local loop):

```bash
uv sync                    # create the environment
uv run poe check           # format + lint + typecheck + lint-imports + deptry (what CI runs)
uv run poe format          # ruff format --check
uv run poe format:fix      # ruff format
uv run poe lint            # ruff check
uv run poe lint:fix        # ruff check --fix
uv run poe lint:md         # markdownlint over all Markdown (via prek)
uv run poe typecheck       # ty check
uv run poe lint-imports    # import-linter layer contracts
uv run poe deptry          # dependency hygiene
uv run poe tests           # pytest with coverage
uv run poe docs            # strict docs site build (what docs CI runs)
uv run poe docs:dev        # serve the docs site with live reload
```

Run `uv run poe check` and `uv run poe tests` before pushing - they are the same checks the pull request runs.
Markdown is not in `poe check` - the prek hook lints it on every commit and in CI; `uv run poe lint:md` runs it on demand.
`poe check` does not build the documentation site either, so run `uv run poe docs` when the change touches `docs/`.

### Tests

`uv run poe tests` runs the suite; CI runs it on Python 3.13, 3.14 and 3.15.
`tests/conftest.py` patches the pyinfra context so rune and operation calls are no-ops - molds, smithy helpers, runes, and templates unit-test without a real target.
End-to-end correctness is still validated by deploying to a real host.

The suite also enforces the [conventions](https://wlix13.github.io/NullForge/contributing/conventions/): operation-emitting loops must go through `host.loop`, and import contracts reject cross-layer imports.

## Commits

All commits are expected to follow the conventional commits specification.

```text
<type>[scope]: <description>
```

It's not a really big deal if you don't, but the commits in your PR might be squashed into a single commit
with the appropriate format at the reviewer's discretion.

Here's a few examples of good commit messages:

- `feat(api): Add endpoint to retrieve images`
- `fix(alerting): Remove bad parameter from Slack alerting provider`
- `test(security): Add tests for basic auth with bcrypt`
- `docs: Add paragraph on running the application locally`

## Pull requests

The **pull request title** should be a short, meaningful summary of the change as a
whole, written in the imperative mood. GitHub pre-fills it with your first commit
message — please replace that with something descriptive. Examples:

- `Add tor rune with bridge support`
- `Improve CI/CD caching and test matrix`
- `Fix swap sizing on small hosts`

A good title reads cleanly in the PR list and the project history. The individual
**commits** inside the PR still follow Conventional Commits (see [Commits](#commits));
because PRs are merged with a merge/rebase strategy, those commit messages — not the
title — drive the release changelog, so the title itself does not need a `type:` prefix.

PRs are labelled automatically from the files they touch (e.g. `runes`, `molds`,
`ci-cd`, `docs`) and from the **Type of change** checklist in the PR template — tick the
boxes that apply and the matching `feature` / `bug` / `enhancement` / `refactor` /
`breaking-change` / `security` label is added. Dependabot PRs are labelled `dependencies`.
