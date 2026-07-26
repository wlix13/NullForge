# Shell profiles

A complete terminal environment: modern CLI tools system-wide, plus per-user shell, editor and multiplexer setups.

**Rune:** `profiles` - **Active when:** `for_root or for_user` - **Default:** on for root

## System-wide tools

Installed once, for all users; pinned tools re-install when their [pin](../guides/version-pinning.md) changes:

| Tool | How |
| --- | --- |
| [eza](https://github.com/eza-community/eza) | pinned release binary |
| [tmux](https://github.com/tmux/tmux) | built from source at the pinned version (distro package removed) |
| [neovim](https://neovim.io) | pinned AppImage extracted to `/usr/bin/nvim-source`, symlinked as `nvim` |
| [zoxide](https://github.com/ajeetdsouza/zoxide) | official install script |
| [direnv](https://direnv.net) | pinned release binary |
| [starship](https://starship.rs) | distro repo on Debian 13 / Ubuntu 25, install script elsewhere |

## Per-user setup

Applied to root (`for_root`), the [managed user](users.md) (`for_user`), or both:

- **oh-my-zsh** plus plugins: `zsh-autosuggestions`, `zsh-syntax-highlighting`, `ohmyzsh-full-autoupdate`.
- **`.zshrc`** - the generated part lives in a marked block (`# ... NULLFORGE MANAGED BLOCK`) *prepended* to the file, so your own lines stay below and win.
  Everything outside the markers survives re-deploys.
- **starship** prompt config and **direnv** config under `~/.config`.
- **tmux** - TPM plugin manager plus a config in `~/.config/tmux`.
- **neovim** - [NvChad](https://nvchad.com) starter with a cursor-restore patch and the `tokyonight` theme; skipped when a `chadrc.lua` already exists so your editor config is never clobbered.
- **atuin** shell history.
- **Nerd Font** (optional) - one family from the [`nerd-fonts`](https://github.com/ryanoasis/nerd-fonts) release, installed to `~/.local/share/fonts` in a versioned directory, `fc-cache` refreshed.

!!! note "First deploy on a pre-existing `.zshrc`"

    A `.zshrc` that predates the managed markers is cleared once (with a backup) before the block is written - otherwise the block would be prepended to a stale copy of itself.
    From then on, hand edits outside the markers are preserved.

## Configuration (`features.profiles`)

| Field | Default | Description |
| --- | --- | --- |
| `for_root` | `true` | Provision root's environment |
| `for_user` | `false` | Provision the managed user's environment |
| `reinstall` | `false` | Reinstall tools and re-clone plugin/editor repos even when present |
| `font` | `None` | Nerd Font family (`JetBrainsMono`, `Hack`, `Meslo`, ... - 22 curated families); `None` skips fonts |

`reinstall` is the recovery lever: oh-my-zsh, plugins, TPM and NvChad are git clones that are otherwise left alone once present.

## Example

```python
from nullforge.models.profiles import NerdFont
from nullforge.molds import ProfilesMold

profiles = ProfilesMold(for_user=True, font=NerdFont.JETBRAINS_MONO)
```
