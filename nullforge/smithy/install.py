"""Release-binary installation helper for NullForge.

`install_release_binary` "centralises download -> verify -> extract -> locate -> install"
dance that every pinned-tool rune used to hand-roll.

- auto-detect archive format from URL (tar.gz/xz/bz2, plain tar, zip, gzip, or raw/AppImage binary)
- verifies download against sha256, resolving it from GitHub release metadata when not supplied
- extracts and locates executable inside the archive, and installs it to `dest` with requested mode
"""

import shlex
from pathlib import PurePosixPath

from pyinfra import logger
from pyinfra.api.operation import OperationMeta
from pyinfra.operations import files, server

from nullforge.smithy.github import sha256_for_download_url
from nullforge.smithy.versions import Versions


STAGING_DIR = "/var/lib/nullforge/staging"
"""Scratch space for archives and their extracted contents."""


# Archive kind -> the tar/unzip/gunzip commands that unpack it into `workdir`.
_TAR_FLAGS = {
    "tar.gz": "-xzf",
    "tar.xz": "-xJf",
    "tar.bz2": "-xjf",
    "tar": "-xf",
}
# Ordered longest-suffix-first so `.tar.gz` wins over `.gz`.
_SUFFIX_KINDS: tuple[tuple[str, str], ...] = (
    (".tar.gz", "tar.gz"),
    (".tgz", "tar.gz"),
    (".tar.xz", "tar.xz"),
    (".txz", "tar.xz"),
    (".tar.bz2", "tar.bz2"),
    (".tbz2", "tar.bz2"),
    (".tar", "tar"),
    (".zip", "zip"),
    (".appimage", "raw"),
    (".gz", "gzip"),
)


def detect_archive(url_or_name: str) -> str:
    """Classify URL/filename as `tar.gz`/`tar.xz`/`tar.bz2`/`tar`/`zip`/`gzip`/`raw`."""

    name = url_or_name.rsplit("/", 1)[-1].lower()
    for suffix, kind in _SUFFIX_KINDS:
        if name.endswith(suffix):
            return kind
    return "raw"


def _extract_commands(kind: str, archive: str, workdir: str, binary_name: str) -> list[str]:
    if kind in _TAR_FLAGS:
        return [f"tar {_TAR_FLAGS[kind]} {shlex.quote(archive)} -C {shlex.quote(workdir)}"]
    if kind == "zip":
        return [f"unzip -o {shlex.quote(archive)} -d {shlex.quote(workdir)}"]
    if kind == "gzip":
        target = f"{workdir}/{binary_name}"
        return [f"gunzip -c {shlex.quote(archive)} > {shlex.quote(target)}"]
    raise ValueError(f"{kind} is not an extractable archive kind")


def install_release_binary(
    *,
    name: str,
    url: str,
    dest: str,
    binary_name: str | None = None,
    sha256: str | None = None,
    verify: bool = True,
    archive: str | None = None,
    mode: str = "0755",
    sudo: bool = True,
    retries: int = 3,
    retry_delay: int = 10,
) -> OperationMeta:
    """Download, verify, extract and install release binary; return install operation.

    `url` is a release-asset URL, usually straight from `Versions` builder,
    and `dest` is absolute path executable ends up at; `name` is what pyinfra prints for install op.

    Integrity is best-effort by design: `sha256` pins checksum, and leaving it unset has `verify`
    resolve one from `url`'s GitHub release metadata instead.
    A repo that publishes no checksums therefore installs unverified.

    Archive kind is detected from `url` unless `archive` forces one, and executable is picked out
    of it by `binary_name`, which defaults to `dest` basename.
    """

    binary_name = binary_name or PurePosixPath(dest).name
    kind = archive or detect_archive(url)
    checksum = sha256 if sha256 is not None else (sha256_for_download_url(url) if verify else None)
    if verify and checksum is None:
        logger.warning(f"No sha256 could be resolved for {url}; installing {name} without integrity verification")

    if kind == "raw":
        return files.download(
            name=name,
            src=url,
            dest=dest,
            mode=mode,
            force=True,
            sha256sum=checksum,
            extra_curl_args=Versions.release_curl_args(url),
            _sudo=sudo,
            _retries=retries,
            _retry_delay=retry_delay,
        )

    download_path = f"{STAGING_DIR}/{PurePosixPath(url).name}"
    workdir = f"{STAGING_DIR}/{binary_name}"

    files.directory(
        name=f"Ensure staging directory for {name}",
        path=STAGING_DIR,
        mode="0700",
        _sudo=sudo,
    )

    files.download(
        name=f"Download {name}",
        src=url,
        dest=download_path,
        force=True,
        sha256sum=checksum,
        extra_curl_args=Versions.release_curl_args(url),
        _sudo=sudo,
        _retries=retries,
        _retry_delay=retry_delay,
    )

    located = f'"$(find {shlex.quote(workdir)} -type f -name {shlex.quote(binary_name)} | head -n1)"'
    return server.shell(
        name=name,
        commands=[
            f"rm -rf {shlex.quote(workdir)} && mkdir -p {shlex.quote(workdir)}",
            *_extract_commands(kind, download_path, workdir, binary_name),
            f"install -D -m {mode} {located} {shlex.quote(dest)}",
            f"rm -rf {shlex.quote(workdir)} {shlex.quote(download_path)}",
        ],
        _sudo=sudo,
    )
