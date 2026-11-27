"""Profiles configuration mold."""

from pydantic import Field

from nullforge.models.profiles import NerdFont

from .base_mold import BaseMold


class ProfilesMold(BaseMold):
    for_root: bool = Field(
        default=True,
        description="Whether to install the profiles for the root user",
    )
    reinstall: bool = Field(
        default=False,
        description="Whether to reinstall profiles and tools even if already installed",
    )
    font: NerdFont | None = Field(
        default=None,
        description="Nerd Font family to install on the target; `None` skips font installation",
    )
    users: list[str] = Field(
        default_factory=list,
        description="Names of users to profile; each name must exist in features.users",
    )

    @property
    def is_active(self) -> bool:
        return self.for_root or bool(self.users)
