"""Containers configuration mold."""

from pydantic import Field

from nullforge.models.containers import ContainersBackendType

from .base_mold import BaseMold


class ContainersMold(BaseMold):
    install: bool = Field(
        default=False,
        description="Whether to install containers backend",
    )
    backend_type: ContainersBackendType = Field(
        default=ContainersBackendType.DOCKER,
        description="Which containers backend to use",
    )
    skopeo: bool = Field(
        default=True,
        description="Whether to install skopeo",
    )

    @property
    def is_active(self) -> bool:
        return self.install
