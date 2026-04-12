"""Containers configuration models."""

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, Field


class ContainersBackendType(StrEnum):
    DOCKER = "docker"
    PODMAN = "podman"
    CRIO = "crio"


class ContainersRuntimeType(StrEnum):
    DEFAULT = "default"
    CRUN = "crun"
    GVISOR = "gvisor"


class _ContainersBackendBase(BaseModel):
    """Base for a containers backend."""

    type: ContainersBackendType = Field(description="The type of containers backend")
    runtime: ContainersRuntimeType = Field(description="The type of containers runtime")


class DockerContainersBackend(_ContainersBackendBase):
    type: Literal[ContainersBackendType.DOCKER] = ContainersBackendType.DOCKER
    runtime: Literal[ContainersRuntimeType.GVISOR] = ContainersRuntimeType.GVISOR


class PodmanContainersBackend(_ContainersBackendBase):
    type: Literal[ContainersBackendType.PODMAN] = ContainersBackendType.PODMAN
    runtime: Literal[ContainersRuntimeType.CRUN] = ContainersRuntimeType.CRUN


class CrioContainersBackend(_ContainersBackendBase):
    type: Literal[ContainersBackendType.CRIO] = ContainersBackendType.CRIO
    runtime: Literal[ContainersRuntimeType.DEFAULT] = ContainersRuntimeType.DEFAULT


ContainersBackend = Annotated[
    DockerContainersBackend | PodmanContainersBackend | CrioContainersBackend,
    Field(discriminator="type"),
]


def containers_backend_factory(type: ContainersBackendType) -> ContainersBackend:
    """Factory function for containers backends."""

    match type:
        case ContainersBackendType.DOCKER:
            return DockerContainersBackend()
        case ContainersBackendType.PODMAN:
            return PodmanContainersBackend()
        case ContainersBackendType.CRIO:
            return CrioContainersBackend()
        case _:
            raise ValueError(f"Unknown ContainersBackendType: {type}")
