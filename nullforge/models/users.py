"""User configuration models."""

from enum import StrEnum


class Shell(StrEnum):
    BASH = "/bin/bash"
    ZSH = "/bin/zsh"
    ZSH_USER = "/usr/bin/zsh"


class UserRole(StrEnum):
    ADMIN = "admin"
    DEPLOY = "deploy"
    NONE = "none"
