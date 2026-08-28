# Conventions

The rules below keep casts deterministic and idempotent.
Most are enforced by tests or CI; the reasoning is documented here so violations are recognizable in review.

## host.loop

**Any loop that emits operations must iterate `host.loop(...)`.**

pyinfra derives an operation's identity from its call-site line numbers.
A call site reached twice gets a `-0` suffix on the second hit; which iteration counts as "second" then depends on fact-guarded emission, so hosts can disagree on operation order - and the whole run aborts with `Cycle detected in operation ordering DAG` before anything executes.
`host.loop` keys the hash to the iteration index instead, which is stable across hosts.

```python
for rule in host.loop(active_rules):
    server.shell(name=f"Apply {rule.comment}", commands=[...], _sudo=True)
```

Never `break` out of a `host.loop`: the loop position is only popped when the iterator is exhausted.

## Change detection

Every config-writing operation returns an `OperationMeta`.
Capture it and guard follow-ups with it:

```python
config = files.template(...)

systemd.service(..., restarted=True, _if=config.did_change)
systemd.daemon_reload(..., _if=config.did_change)
```

- Use `any_changed(op1, op2, ...)` (from `pyinfra.operations.util`) when several prior ops should trigger one restart/reload.
- Prefer a **conditional** "restart on change" plus an **unconditional** "ensure running/enabled".
- `_if=` expects callables (or a list of them).
  `_if=op.will_change` passes a bare boolean and is silently ignored - always `did_change`/`did_succeed` references.
- Plain `if op.will_change:` is for **prepare-time decisions that emit more operations** only (rare - the GRUB regeneration in `base.py` is the canonical case).

## Version-pinned installers

Installers for pinned tools guard with `is_pinned_version_installed(tool, binary_path)` - not a bare `File` fact - so a pin bump triggers re-install.
Past the guard, call `install_release_binary()` rather than hand-rolling download/extract: it force-downloads, verifies the sha256 when one is passed or resolved from GitHub release metadata (best-effort - when no checksum is available it installs unverified and logs a warning), extracts any archive kind, and returns the install `OperationMeta` for restart chaining.

Keep the guard at the call site: checksum resolution makes a plan-time API call, so the helper should only be reached when an install is actually pending.

Non-fitting installers stay custom: source builds (tmux), AppImage-to-directory extraction (nvim), and non-GitHub / `latest` / multi-binary downloads (gVisor).

## Downloads

Every `curl` NullForge runs on a target takes its options from `smithy.http.curl_args(url)` - `curl_args_str(url)` for hand-written commands, `Versions.release_curl_args(url)` for GitHub release assets - never the bare `CURL_ARGS` dict.
The helpers probe the URL at plan time and fall back to the [WARP interface](../features/warp.md#downloads-through-warp) when the direct route is filtered, so a DPI-blocked uplink does not break installs.
Because the probe is a live request, call them behind the install guard - like `install_release_binary()` - not for downloads that will be no-ops.

## Fact handling

Don't wrap `host.get_fact(...)` in `contextlib.suppress` - facts never raise to the caller, so the guard is dead code.
Handle return values instead: `FileContents` is `None` for a missing or unreadable file, and `Command` facts return empty output rather than failing the host.

## User-editable config files

Files users are expected to edit (`.zshrc`, nvim's `init.lua`) are written with `files.block` and a `{mark}` marker - never `files.template` - so everything outside the markers survives re-deploys.

`.zshrc` prepends its block (`before=True, after=True`) so user lines come last and win.
A file predating the markers is detected via the `Block` fact returning `[]` and cleared once with `files.line(line=".*", present=False, backup=True)` - otherwise the block would be prepended to a stale copy of itself.

## Code style

- Private helpers within rune/smithy files are `_`-prefixed.
- Type annotations everywhere; `ty` is the checker.
- Line length 120; ruff rules `E, F, I, N, S, UP, W, YTT`.
- [Import-layer contracts](../concepts/architecture.md#layer-contracts) are part of `poe check` - new modules must respect the spine.
- Docs prose is one sentence per line; markdownlint runs over all Markdown via prek.
