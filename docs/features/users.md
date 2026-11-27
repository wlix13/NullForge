# Users

Creates and maintains the host's users with role-scoped permissions.

**Rune:** `users` - **Active when:** `features.users` list is non-empty - **Default:** on (user core, admin role)

## What it deploys

For each user in the list:

- Creates the user with the configured shell and a home directory, appending it to the sudo group (`sudo` on Debian/Ubuntu, `wheel` on RHEL) when role is `admin`.
- **Password**: applied when set; for `admin` role with no password, passwordless sudo is configured via `/etc/sudoers.d/<name>`. For `deploy` role, passwordless sudo is limited to explicit `sudo_commands` (always written, even if password is set). For `none` role, any existing drop-in is removed.
- **SSH keys**: merges literal `ssh_keys`, keys copied from the connecting user's `authorized_keys` (when `copy_root_keys`), and/or fetched from a GitHub account, deduplicates them, and installs them with correct ownership and modes.
- Optionally sets root's shell to match the user's (when `set_root_shell_like_user`).

## Configuration (`features.users`)

`features.users` is a `UsersMold` containing a list of `UserMold` objects.
Each entry has these fields:

| Field | Default | Description |
| --- | --- | --- |
| `name` | required | Username (portable filename charset enforced; cannot be `root`, `ALL`, `.`, `..`) |
| `role` | `UserRole.NONE` | Access role: `admin`, `deploy`, or `none` |
| `password` | `None` | Login password |
| `sudo_commands` | `None` | Required non-empty list of absolute command paths for `deploy` role; forbidden on `admin` and `none` |
| `shell` | `Shell.ZSH` | `Shell.BASH`, `Shell.ZSH`, or `Shell.ZSH_USER` (`/usr/bin/zsh`) |
| `ssh_keys` | `[]` | Literal SSH public keys to install |
| `fetch_key_from_github` | `None` | GitHub username whose public keys to import |
| `copy_root_keys` | `false` | Copy the connecting user's `authorized_keys` |
| `set_root_shell_like_user` | `false` | Sync root's shell to this user's shell |

`password` is redacted in `--debug-inventory` output for every list entry.
Passwords must not contain control characters (ASCII below 0x20 or 0x7f).

### Roles (`UserRole`)

| Role | Sudo group | Sudoers drop-in | Container runtime access |
| --- | --- | --- | --- |
| `admin` (`UserRole.ADMIN`) | `sudo` (Debian/Ubuntu) or `wheel` (RHEL) | `NOPASSWD:ALL` when `password` is `None` (removed when `password` is set) | `docker` group, subuid/subgid ranges, podman linger |
| `deploy` (`UserRole.DEPLOY`) | none | `NOPASSWD` limited to explicit `sudo_commands` (always written, even if `password` is set) | none |
| `none` (`UserRole.NONE`) | none | none (existing drop-in removed) | none |

Sudoers drop-in filenames sanitize characters outside `[A-Za-z0-9_-]` to `_` so `/etc/sudoers.d` never ignores names containing dots, and colliding sanitized filenames across managed users are rejected.

!!! note "Layer merging and user removal"

    `merge_features` replaces list fields wholesale, so a layer setting `users` overwrites the entire list from earlier layers rather than appending to it.
    Removing a user from `users` does not delete the OS account, home directory, or sudoers drop-in on the host.

!!! warning "Keep at least one key source"

    Nothing rejects a user with `copy_root_keys = false`, `fetch_key_from_github = None`, and `ssh_keys = []`.
    The user is then created without SSH keys while [network security](netsec.md) disables password authentication and root login - locking you out of SSH on the next cast.

## Interactions

- [Network security](netsec.md) disables SSH password authentication (and root login) when `users` rune is active (i.e., `features.users` list is non-empty).
- [Containers](containers.md) grants `docker` group membership, subuid/subgid ranges, and rootless podman linger to `admin` users only.
- [Shell profiles](profiles.md) provisions the shell environment for each user listed in `features.profiles.users`.
- [HAProxy](haproxy.md) and [Xray](xray.md) grant all users ACL access to their config directories.

!!! warning "zsh before the profiles rune"

    The default shell is zsh, which the base package set installs.
    If you disable the base packages, make sure the configured shell exists - `server.user` does not install it.

## Example

```python
from nullforge.models.users import UserRole
from nullforge.molds import UserMold, UsersMold

users = UsersMold(
    users=[
        UserMold(
            name="ops",
            role=UserRole.ADMIN,
            fetch_key_from_github="your-github-username",
        ),
        UserMold(
            name="ci-deploy",
            role=UserRole.DEPLOY,
            sudo_commands=[
                "/usr/bin/systemctl restart app.service",
                "/usr/bin/systemctl status app.service",
            ],
            shell=Shell.BASH,
            ssh_keys=["ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIExampleDeployKey ci-deploy@example"],
        ),
    ]
)
```
