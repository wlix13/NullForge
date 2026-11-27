# CLI reference

```text
nullforge [-V] COMMAND [ARGS]...
```

Three commands: `cast`, `runes`, and `completion`.

## `nullforge cast`

Cast runes onto an inventory via pyinfra.

```bash
nullforge cast -i INVENTORY [-r RUNE]... [OPTIONS] [PYINFRA_ARGS]...
```

| Option | Description |
| --- | --- |
| `-i, --inventory` | **Required.** Inventory `.py` file or raw host spec (`@local`, `host1,host2`). |
| `-r, --rune` | Built-in rune name or path to a custom rune file; repeatable, runs in order. Omit to run the full cast. |
| `--with-prepare` | Run the `prepare` rune as a separate first deploy (fresh hosts without sudo). |
| `--dry` | Don't execute operations on the target hosts. |
| `--diff` | Show file and template differences. |
| `-y, --yes` | Execute operations without prompting. |
| `--debug` | Print pyinfra debug logs. |
| `-v` | Print operation meta (`-v`), input (`-vv`) and output (`-vvv`). |
| `--ssh-user` | SSH user to connect as. |
| `--ssh-port` | SSH port to connect to. |
| `--ssh-key` | SSH private key file. |
| `--ssh-key-password` | SSH private key password. |
| `--ssh-password` | SSH password. |
| `--sudo-user` | User to sudo as. |
| `--parallel` | Number of hosts to run in parallel. |
| `--limit` | Restrict target hosts by name or group; repeatable. |
| `--data` | Override target data (`key=value`); repeatable. |

### pyinfra pass-through

Unknown options are passed through to pyinfra verbatim, so anything from `pyinfra --help` works:

```bash
nullforge cast -i inventory.py -r dns --ssh-user root --ssh-port 2222 --dry -v
```

### Host specs

`-i` accepts either an inventory file or a raw spec:

```bash
nullforge cast -i "@local" -r base        # local machine, no SSH
nullforge cast -i host1,host2 -r netsec   # ad-hoc host list
```

Raw specs carry no `system`/`features` data, so every feature falls back to its mold defaults; use `--data` for point overrides.

!!! note "PowerShell"

    Quote `@local`-style specs (`-i "@local"`) - unquoted `@name` is PowerShell splatting syntax and is swallowed by the shell.

### Stages

A cast resolves into one or two pyinfra invocations:

- `--with-prepare` runs `prepare` alone first, so the main deploy gathers facts after `sudo` exists.
- With `-r`, the selected runes run in the given order (deduplicated).
- Without `-r`, the full cast runs: `prepare`, `base`, then every [active feature](../features/index.md) in declaration order.

## `nullforge runes`

List built-in runes with their one-line summaries.

```bash
nullforge runes
```

## `nullforge completion`

Print or install shell completion for `bash`, `zsh`, `fish`, or `powershell`:

```bash
nullforge completion zsh
nullforge completion powershell --install
```

`--install` writes the completion script and registers it in the shell profile.
