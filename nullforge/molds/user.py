"""User configuration mold."""

import re
from typing import ClassVar, Self

from pydantic import Field, field_validator, model_validator

from nullforge.models.users import Shell, UserRole

from .base_mold import BaseMold


_SUDOERS_UNSAFE_RE = re.compile(r"""[\x00-\x1f\x7f,#\\:;*?\[\]!=()\"']""")
_PASSWORD_CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]")


def _sudoers_filename(username: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]", "_", username)


def _validate_password(value: str | None) -> str | None:
    if value is not None and _PASSWORD_CONTROL_RE.search(value):
        raise ValueError("Password cannot contain control characters")
    return value


def _validate_username(value: str) -> str:
    if not value:
        raise ValueError("Name cannot be empty")

    if value.startswith("-"):
        raise ValueError("Name cannot start with a hyphen")

    if value in ("ALL", ".", ".."):
        raise ValueError("Name cannot be a sudoers keyword or path traversal sequence")

    if not re.match(r"^[A-Za-z0-9._-]+$", value):
        raise ValueError("Name must only contain characters from the portable filename character set")

    return value


def _validate_github_username(value: str | None) -> str | None:
    if value is not None and not re.match(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})$", value):
        raise ValueError(f"Invalid GitHub username: {value!r}")

    return value


class UserMold(BaseMold):
    """Per-user entry with role-scoped permissions."""

    _sensitive_fields: ClassVar[tuple[str, ...]] = ("password",)
    name: str = Field(
        description="Username (portable filename charset; cannot be root, ALL, ., ..)",
    )
    role: UserRole = Field(
        default=UserRole.NONE,
        description="Access role: admin, deploy, or none",
    )
    password: str | None = Field(
        default=None,
        description="Login password",
    )
    sudo_commands: list[str] | None = Field(
        default=None,
        description="Allowed sudo commands for deploy role (absolute paths, no metachars)",
    )
    shell: Shell = Field(
        default=Shell.ZSH,
        description="Login shell",
    )
    ssh_keys: list[str] = Field(
        default_factory=list,
        description="Literal SSH public keys",
    )
    fetch_key_from_github: str | None = Field(
        default=None,
        description="GitHub username for SSH public keys",
    )
    copy_root_keys: bool = Field(
        default=False,
        description="Copy connecting user's authorized_keys",
    )
    set_root_shell_like_user: bool = Field(
        default=False,
        description="Set root user's shell to this user's shell",
    )

    @field_validator("name", mode="before")
    @classmethod
    def _validate_name(cls, value: str) -> str:
        value = _validate_username(value)
        if value == "root":
            raise ValueError("User name cannot be 'root'")
        return value

    @field_validator("password")
    @classmethod
    def _validate_password(cls, value: str | None) -> str | None:
        return _validate_password(value)

    @field_validator("fetch_key_from_github")
    @classmethod
    def _validate_fetch_key_from_github(cls, value: str | None) -> str | None:
        return _validate_github_username(value)

    @model_validator(mode="after")
    def _validate_sudo_commands(self) -> Self:
        if self.role is UserRole.DEPLOY:
            if not self.sudo_commands:
                raise ValueError("sudo_commands must be a non-empty list when role is 'deploy'")
            for cmd in self.sudo_commands:
                if (
                    cmd.strip() == "ALL"
                    or not re.match(r"^/[^\s/]", cmd)
                    or cmd.rstrip().endswith("/")
                    or cmd.split()[0].endswith("/")
                    or _SUDOERS_UNSAFE_RE.search(cmd)
                ):
                    raise ValueError(f"Invalid sudoers command: {cmd!r}")
        elif self.sudo_commands is not None:
            raise ValueError("sudo_commands is only allowed when role is 'deploy'")
        return self

    @property
    def shell_path(self) -> str:
        return self.shell.value


class UsersMold(BaseMold):
    """Role-carrying list of users with validation and rune dispatch support."""

    _sensitive_fields: ClassVar[tuple[str, ...]] = ()

    users: list[UserMold] = Field(default_factory=list)

    @property
    def is_active(self) -> bool:
        return bool(self.users)

    def __iter__(self):
        return iter(self.users)

    def __len__(self):
        return len(self.users)

    def __getitem__(self, idx):
        return self.users[idx]

    @model_validator(mode="after")
    def _validate_users_unique(self):
        seen: set[str] = set()
        seen_sudoers: dict[str, str] = {}
        for user in self.users:
            if user.name in seen:
                raise ValueError(f"Duplicate user name: {user.name!r}")
            sudoers_name = _sudoers_filename(user.name)
            if sudoers_name in seen_sudoers:
                other = seen_sudoers[sudoers_name]
                raise ValueError(f"User {user.name!r} sudoers filename {sudoers_name!r} collides with {other!r}")
            seen.add(user.name)
            seen_sudoers[sudoers_name] = user.name
        return self
