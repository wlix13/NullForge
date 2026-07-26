# Feature reference

Each feature is a sub-mold of `FeaturesMold` paired with a [rune](../concepts/runes.md).
The full cast visits features in the order below and deploys the ones whose `is_active` is true.

`prepare` and `base` are not features - they [always run first](base.md).

| Feature | Rune | Default | Active when |
| --- | --- | --- | --- |
| [DNS](dns.md) | `dns` | **on** (Blocky) | `mode != "none"` |
| [Users](users.md) | `users` | **on** | `manage = true` |
| [Network security](netsec.md) | `netsec` | **on** | `install = true` |
| [Shell profiles](profiles.md) | `profiles` | **on** (root only) | `for_root or for_user` |
| [Cloudflare WARP](warp.md) | `warp` | off | `install = true` |
| [Zero Trust Tunnel](zerotrust.md) | `zerotrust` | off | `install = true` |
| [Containers](containers.md) | `containers` | off | `install = true` |
| [Monitoring](monitoring.md) | `monitoring` | off | `install = true` |
| [HAProxy](haproxy.md) | `haproxy` | off | `install = true` |
| [Xray](xray.md) | `xray` | off | `install = true` |
| [Tor](tor.md) | `tor` | off | `install = true` |
| [Telemt](telemt.md) | `telemt` | off | `install = true` |

Turning a default-on feature off is a one-line layer:

```python
merge_features(BASE_FEATURES, {"dns": {"mode": "none"}, "profiles": {"for_root": False}})
```

Every page in this section documents the feature's behaviour, its configuration fields with defaults, and an inventory fragment to start from.
