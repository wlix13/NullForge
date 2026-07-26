# Users

Creates and maintains the host's admin user.

**Rune:** `users` - **Active when:** `manage = true` - **Default:** on (user `core`)

## What it deploys

- Creates the user with the configured shell and a home directory, appending it to the sudo group (`sudo` on Debian/Ubuntu, `wheel` on RHEL) when `sudo` is set.
- **Password**: applied when set; with no password and `sudo` on, passwordless sudo is configured via `/etc/sudoers.d/<name>`.
- **SSH keys**: merges keys copied from the connecting user's `authorized_keys` (root's, in the usual root bootstrap - hence `copy_root_keys`) and/or fetched from a GitHub account, deduplicates them, and installs them with correct ownership and modes (plus a `~/.ssh/sockets` directory for multiplexing).
- Optionally sets root's shell to match the user's.

## Configuration (`features.users`)

| Field | Default | Description |
| --- | --- | --- |
| `manage` | `true` | Manage the user at all |
| `name` | `"core"` | Username (portable filename charset enforced) |
| `password` | `None` | Password; `None` + `sudo` => passwordless sudo |
| `sudo` | `true` | Add to the sudo/wheel group |
| `shell` | `"/bin/zsh"` | `Shell.BASH`, `Shell.ZSH`, or `Shell.ZSH_USER` (`/usr/bin/zsh`) |
| `copy_root_keys` | `true` | Copy the connecting user's `authorized_keys` |
| `fetch_key_from_github` | `None` | GitHub username whose public keys to import |
| `set_root_shell_like_user` | `true` | Sync root's shell to the user's |

`password` is redacted in `--debug-inventory` output.

!!! warning "Keep at least one key source"

    Nothing rejects `manage = true` with both `copy_root_keys = false` and `fetch_key_from_github = None`.
    The user is then created without SSH keys while [network security](netsec.md) disables password authentication and root login - locking you out of SSH on the next cast.

## Interactions

- [Network security](netsec.md) disables SSH password authentication (and root login) when `users.manage` is true - keep at least one key source enabled so you can still log in.
- [Containers](containers.md) adds this user to the `docker` group.
- [Shell profiles](profiles.md) with `for_user = true` provisions this user's shell environment.
- [HAProxy](haproxy.md) and [Xray](xray.md) grant this user ACL access to their config directories.

!!! warning "zsh before the profiles rune"

    The default shell is zsh, which the base package set installs.
    If you disable the base packages, make sure the configured shell exists - `server.user` does not install it.

## Example

```python
users = UserMold(
    name="ops",
    fetch_key_from_github="your-github-username",
    copy_root_keys=False,
)
```
