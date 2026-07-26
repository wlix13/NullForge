# Containers

A container runtime with a sandboxed-by-default configuration.

**Rune:** `containers` - **Active when:** `install = true` - **Default:** off

## Backends

| Backend | Runtime | Notes |
| --- | --- | --- |
| `docker` (default) | [gVisor](https://gvisor.dev) (`runsc`) | Docker Engine via the official install script |
| `podman` | crun | `podman` + `podman-compose` from the distro |
| `crio` | - | not supported yet (fails at plan time) |

### docker

- Installs Docker Engine with the official `get.docker.com` script (skipped when `docker` is already present).
- Adds the [managed user](users.md) to the `docker` group when `users.manage` is on.
- Installs gVisor and registers `runsc`:
  on Debian/Ubuntu from the official APT repository;
  on RHEL by fetching `runsc` + containerd shim binaries, then `runsc install` promotes it to Docker's **default runtime** (with a daemon reload).

!!! note "gVisor is the default runtime"

    Containers run under gVisor's user-space kernel unless started with an explicit `--runtime`.
    Workloads that need raw kernel features (e.g. some eBPF users) should override the runtime per container.

### podman

Installs `podman`, `podman-compose`, and the `crun` runtime from distro packages - no scripts, no extra repos.

## Configuration (`features.containers`)

| Field | Default | Description |
| --- | --- | --- |
| `install` | `false` | Deploy a container backend |
| `backend_type` | `"docker"` | `docker`, `podman`, or `crio` |
| `skopeo` | `true` | Also install [skopeo](https://github.com/containers/skopeo) for registry operations |

## Example

```python
from nullforge.molds import ContainersMold

containers = ContainersMold(install=True)
```
