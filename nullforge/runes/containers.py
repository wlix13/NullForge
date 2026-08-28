"""Containers deployment module."""

from pyinfra.context import host
from pyinfra.facts.files import File
from pyinfra.facts.server import Arch, Which
from pyinfra.operations import apt, files, server, systemd

from nullforge.models.containers import ContainersBackendType
from nullforge.molds import ContainersMold, FeaturesMold, UserMold
from nullforge.smithy.arch import deb_arch
from nullforge.smithy.http import curl_args
from nullforge.smithy.packages import get_pm
from nullforge.smithy.versions import GPG_KEYS, STATIC_URLS


def deploy_containers() -> None:
    """Deploy containers runtime and related tools."""

    features: FeaturesMold = host.data.features
    containers_opts: ContainersMold = features.containers
    user_opts: UserMold = features.users

    match containers_opts.backend_type:
        case ContainersBackendType.DOCKER:
            _install_docker()
            if user_opts.manage:
                _add_user_to_docker_group(user_opts.name)
            _install_gvisor()
        case ContainersBackendType.PODMAN:
            _install_crun()
            _install_podman()
        case ContainersBackendType.CRIO:
            raise ValueError("CRIO is not supported yet")

    if containers_opts.skopeo:
        _install_skopeo()


def _install_gvisor() -> None:
    """Install gVisor runtime."""

    pm = get_pm()
    if pm.is_debian_based:
        _install_gvisor_debian()
    elif pm.is_rhel_based:
        _install_gvisor_rhel()
    else:
        host.noop(f"gVisor install skipped: unsupported distro {pm.distro_name}")


def _install_gvisor_debian() -> None:
    """Install gVisor on Debian/Ubuntu via the official APT repo."""

    gvisor_key_path = "/usr/share/keyrings/gvisor-archive-keyring.gpg"
    apt.key(
        name="Install gVisor GPG key",
        src=GPG_KEYS["gvisor"],
        dest=gvisor_key_path,
        _sudo=True,
        _retries=3,
        _retry_delay=10,
    )

    apt.sources_file(
        name="Write gVisor repository source",
        filename="gvisor",
        uris="https://storage.googleapis.com/gvisor/releases",
        suites="release",
        components="main",
        architectures=deb_arch(),
        signed_by=gvisor_key_path,
        _sudo=True,
    )

    pm = get_pm()
    pm.update(
        name="Update package repositories after adding gVisor repository",
        _sudo=True,
    )

    pm.install(
        name="Install gVisor",
        packages=["runsc"],
        _sudo=True,
    )


def _install_gvisor_rhel() -> None:
    """Install gVisor binaries manually and register as Docker's default runtime."""

    runsc_path = "/usr/local/bin/runsc"
    if host.get_fact(File, runsc_path):
        host.noop("gVisor already installed")
        return

    arch = host.get_fact(Arch)
    base_url = f"https://storage.googleapis.com/gvisor/releases/release/latest/{arch}"
    runsc_url = f"{base_url}/runsc"
    shim_url = f"{base_url}/containerd-shim-runsc-v1"

    files.download(
        name="Download gVisor runsc binary",
        src=runsc_url,
        dest=runsc_path,
        mode="0755",
        extra_curl_args=curl_args(runsc_url),
        _sudo=True,
        _retries=3,
        _retry_delay=10,
    )

    files.download(
        name="Download gVisor containerd-shim",
        src=shim_url,
        dest="/usr/local/bin/containerd-shim-runsc-v1",
        mode="0755",
        extra_curl_args=curl_args(shim_url),
        _sudo=True,
        _retries=3,
        _retry_delay=10,
    )

    register_runtime = server.shell(
        name="Register gVisor as Docker's default runtime",
        commands=[
            # `runsc install` creates/updates /etc/docker/daemon.json with the runsc runtime entry.
            f"{runsc_path} install",
            # Promote runsc to default-runtime so containers use it without `--runtime=runsc`.
            'jq \'. + {"default-runtime": "runsc"}\' /etc/docker/daemon.json'
            " > /etc/docker/daemon.json.tmp && mv /etc/docker/daemon.json.tmp /etc/docker/daemon.json",
        ],
        _sudo=True,
    )

    systemd.service(
        name="Reload Docker to pick up gVisor runtime",
        service="docker",
        reloaded=True,
        _sudo=True,
        _if=register_runtime.did_change,
    )


def _install_docker() -> None:
    """Install Docker using official installation script."""

    if host.get_fact(Which, command="docker"):
        return

    get_docker_path = "/tmp/get-docker.sh"
    files.download(
        name="Download Docker installation script",
        src=STATIC_URLS["docker_install"],
        dest=get_docker_path,
        mode="0755",
        extra_curl_args=curl_args(STATIC_URLS["docker_install"]),
        _retries=3,
        _retry_delay=10,
    )

    server.shell(
        name="Install Docker",
        commands=[f"bash {get_docker_path}"],
        _sudo=True,
    )


def _add_user_to_docker_group(username: str) -> None:
    """Add user to docker group."""

    server.user(
        name=f"Add user {username} to docker group",
        user=username,
        groups=["docker"],
        append=True,
        _sudo=True,
    )


def _install_skopeo() -> None:
    """Install skopeo."""

    pm = get_pm()
    pm.install(
        name="Install skopeo",
        packages=["skopeo"],
        _sudo=True,
    )


def _install_podman() -> None:
    """Install Podman."""

    pm = get_pm()
    pm.install(
        name="Install Podman",
        packages=[
            "podman",
            "podman-compose",
        ],
        _sudo=True,
    )


def _install_crun() -> None:
    pm = get_pm()
    pm.install(
        name="Install crun",
        packages=["crun"],
        _sudo=True,
    )


deploy_containers()
