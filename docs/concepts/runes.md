# Runes

A rune is one deployable concern: a single pyinfra operation set that is idempotent and self-contained.
Built-in runes live in `nullforge/runes/`, one file each.

```bash
nullforge runes   # list built-in runes with summaries
```

## Execution

Runes are executed, not imported.
The foundry (or the selective `cast.py`) pulls each one in with pyinfra's `local.include`, so the module-level code runs at deploy time with `host` bound to the current target.
Every rune file defines a `deploy_*()` function and calls it at the bottom.

## Dispatch

The full cast derives its rune list from `FeaturesMold` itself:

1. [`prepare` and `base`](../features/base.md) always run first.
2. Every feature field is visited in declaration order; its rune is included when the sub-mold's `is_active` is true.

The rune name defaults to the field name (`warp` -> `runes/warp.py`).
A sub-mold can override it with `_feature_rune = "other-name"`, or opt out of dispatch with `_feature_rune = None`.

## Independence

No rune imports another rune.
Cross-feature coordination happens through configuration instead: a rune may *read* another feature's mold (Telemt reads `features.warp` to set up policy routing) but never calls into another rune's code.

This keeps selective casts honest - `nullforge cast -r telemt` behaves the same whether or not the WARP rune ran in the same invocation.

## Custom runes

`-r` accepts paths as well as built-in names - the [custom runes guide](../guides/custom-runes.md) covers writing your own.
