<!--
PR TITLE: write a short, meaningful summary of the change as a whole, in the
imperative mood - don't leave the auto-filled first-commit message. Examples:
  * Add tor rune with bridge support
  * Improve CI/CD caching and test matrix
  * Fix swap sizing on small hosts
Individual commits should still follow Conventional Commits (see CONTRIBUTING.md);
on merge/rebase those commits drive the release changelog.
-->

## Type of change

<!-- Please check all that apply - this drives the PR's type labels. -->

- [ ] **Bug fix** (fixes an issue in a rune, mold or deploy behaviour)
- [ ] **Feature** (adds a new rune, mold or CLI capability)
- [ ] **Enhancement** (improves existing provisioning logic or output)
- [ ] **Refactor** (restructures code without changing behaviour)
- [ ] **Breaking change** (changes existing mold schemas, CLI usage, or deploy behaviour)
- [ ] **Security** (security-related fix or hardening)

## Description

### Why is this change needed?

<!-- Explain the motivation and context for this change -->

### Related Issues

<!-- Link to related issues using "Fixes #123", "Closes #123", or "Relates to #123" -->

## Testing

<!-- Describe how you tested your changes -->

- [ ] Unit tests added or updated (`uv run poe tests`)
- [ ] Deployed to a real host
- [ ] No testing required (documentation changes only)

## Checklist

<!-- Ensure all applicable items are completed before requesting review -->

- [ ] Code follows project style guidelines
- [ ] Self-review completed
- [ ] Linter and type checker pass (`uv run poe check`)
- [ ] Documentation updated (if applicable)
