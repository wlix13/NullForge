"""Profiles configuration mold."""

from pydantic import Field

from nullforge.models.profiles import NerdFont

from .base_mold import BaseMold


class ProfilesMold(BaseMold):
    for_root: bool = Field(
        default=True,
        description="Whether to install the profiles for the root user",
    )
    for_user: bool = Field(
        default=False,
        description="Whether to install the profiles for the user",
    )
    reinstall: bool = Field(
        default=False,
        description="Whether to reinstall profiles and tools even if already installed",
    )
    font: NerdFont | None = Field(
        default=None,
        description="Nerd Font family to install on the target; `None` skips font installation",
    )

    @property
    def is_active(self) -> bool:
        return self.for_root or self.for_user
