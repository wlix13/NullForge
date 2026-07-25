from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest

from nullforge.smithy import install


class TestDetectArchive:
    @pytest.mark.parametrize(
        ("name", "expected"),
        [
            ("tool-1.2.3.tar.gz", "tar.gz"),
            ("tool.tgz", "tar.gz"),
            ("tool.tar.xz", "tar.xz"),
            ("tool.txz", "tar.xz"),
            ("tool.tar.bz2", "tar.bz2"),
            ("tool.tar", "tar"),
            ("tool.zip", "zip"),
            ("tool.AppImage", "raw"),
            ("tool-linux-amd64.gz", "gzip"),
            ("direnv.linux-amd64", "raw"),
            ("https://github.com/o/r/releases/download/v1/tool.tar.gz", "tar.gz"),
        ],
    )
    def test_detects_kind(self, name: str, expected: str) -> None:
        assert install.detect_archive(name) == expected


class TestExtractCommands:
    def test_raw_is_not_extractable(self) -> None:
        with pytest.raises(ValueError, match="not an extractable"):
            install._extract_commands("raw", "/tmp/tool", "/tmp/work", "tool")


@pytest.fixture
def _wired() -> Generator[MagicMock]:
    """Patch pyinfra ops + checksum/curl helpers; yield a namespace of the mocks."""

    ns = MagicMock()
    with (
        patch.object(install, "files", ns.files),
        patch.object(install, "server", ns.server),
        patch.object(install, "sha256_for_download_url", ns.resolve),
        patch.object(install.Versions, "release_curl_args", return_value={"--resolve": "host:443:1.2.3.4"}),
    ):
        ns.resolve.return_value = "c" * 64
        yield ns


class TestInstallReleaseBinary:
    def test_archive_downloads_then_installs(self, _wired: MagicMock) -> None:
        url = "https://github.com/o/r/releases/download/v1/telemt-x86_64-linux-gnu.tar.gz"
        result = install.install_release_binary(name="Install telemt", url=url, dest="/usr/local/bin/telemt")

        staged = f"{install.STAGING_DIR}/telemt-x86_64-linux-gnu.tar.gz"

        directory = _wired.files.directory.call_args.kwargs
        assert directory["path"] == install.STAGING_DIR
        assert directory["mode"] == "0700"
        assert not install.STAGING_DIR.startswith("/tmp")

        dl = _wired.files.download.call_args.kwargs
        assert dl["src"] == url
        assert dl["dest"] == staged
        assert dl["sha256sum"] == "c" * 64
        assert dl["force"] is True
        assert dl["_sudo"] is True

        shell = _wired.server.shell.call_args.kwargs
        commands = "\n".join(shell["commands"])
        assert f"tar -xzf {staged}" in commands
        assert "-name telemt" in commands
        assert "install -D -m 0755" in commands
        assert shell["_sudo"] is True
        # returns the install op (server.shell), not the download
        assert result is _wired.server.shell.return_value

    def test_raw_binary_is_single_download(self, _wired: MagicMock) -> None:
        url = "https://github.com/direnv/direnv/releases/download/v2.37.1/direnv.linux-amd64"
        result = install.install_release_binary(
            name="Install direnv", url=url, dest="/usr/local/bin/direnv", mode="0755"
        )

        _wired.server.shell.assert_not_called()
        dl = _wired.files.download.call_args.kwargs
        assert dl["dest"] == "/usr/local/bin/direnv"
        assert dl["mode"] == "0755"
        assert dl["sha256sum"] == "c" * 64
        assert result is _wired.files.download.return_value

    def test_explicit_sha256_skips_resolution(self, _wired: MagicMock) -> None:
        install.install_release_binary(
            name="x",
            url="https://github.com/o/r/releases/download/v1/x.tar.gz",
            dest="/usr/local/bin/x",
            sha256="d" * 64,
        )
        _wired.resolve.assert_not_called()
        assert _wired.files.download.call_args.kwargs["sha256sum"] == "d" * 64

    def test_verify_false_skips_checksum(self, _wired: MagicMock) -> None:
        install.install_release_binary(
            name="x",
            url="https://github.com/o/r/releases/download/v1/x.tar.gz",
            dest="/usr/local/bin/x",
            verify=False,
        )
        _wired.resolve.assert_not_called()
        assert _wired.files.download.call_args.kwargs["sha256sum"] is None

    def test_binary_name_defaults_to_dest_basename(self, _wired: MagicMock) -> None:
        install.install_release_binary(
            name="x",
            url="https://github.com/o/r/releases/download/v1/x.tar.gz",
            dest="/usr/local/bin/mytool",
        )
        commands = "\n".join(_wired.server.shell.call_args.kwargs["commands"])
        assert "-name mytool" in commands
