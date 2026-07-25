"""Cloudflare service management module."""

from pyinfra.api.operation import OperationMeta
from pyinfra.context import host
from pyinfra.operations import files

from nullforge.smithy.versions import get_versions, is_pinned_version_installed


CLOUDFLARE_GROUP = "cloudflare"
CLOUDFLARE_USER = "cloudflare"
CLOUDFLARED_BINARY = "/usr/bin/cloudflared"


def ensure_cloudflared_binary() -> OperationMeta | None:
    if is_pinned_version_installed("cloudflared", CLOUDFLARED_BINARY):
        host.noop("cloudflared binary is already installed")
        return None

    return files.download(
        name="Install cloudflared binary",
        src=get_versions().cloudflared_url(),
        dest=CLOUDFLARED_BINARY,
        mode="0755",
        user=CLOUDFLARE_USER,
        group=CLOUDFLARE_GROUP,
        force=True,
        extra_curl_args=get_versions().release_curl_args(),
        _sudo=True,
        _retries=3,
        _retry_delay=10,
    )
