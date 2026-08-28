from collections.abc import Generator
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest

from nullforge.smithy.versions import (
    DEFAULT_VERSIONS,
    RELEASE_ASSET_HOST,
    VERSION_MARKER_DIR,
    Versions,
    is_pinned_version_installed,
    record_installed_version,
)


class _FakeData:
    def __init__(self, overrides: dict | None = None) -> None:
        self._overrides = overrides or {}

    def get(self, key: str, default: object = None) -> object:
        return self._overrides.get(key, default)


@contextmanager
def _versions_context(arch: str = "x86_64", overrides: dict | None = None) -> Generator[Versions]:
    host = MagicMock()
    host.data = _FakeData(overrides)
    host.get_fact.return_value = arch
    with patch("nullforge.smithy.versions._ctx_host", host):
        with patch("nullforge.smithy.arch.host", host):
            yield Versions()


class TestVersionsDefaults:
    def test_uses_default_versions(self) -> None:
        with _versions_context() as v:
            assert v.versions["blocky"] == DEFAULT_VERSIONS["blocky"]

    def test_host_overrides_merge(self) -> None:
        with _versions_context(overrides={"versions": {"blocky": "v99.0"}}) as v:
            assert v.versions["blocky"] == "v99.0"


class TestArchSelect:
    def test_x86_64_selects_first(self) -> None:
        with _versions_context("x86_64") as v:
            assert v._arch_select("amd64", "arm64") == "amd64"

    def test_arm64_selects_second(self) -> None:
        with _versions_context("arm64") as v:
            assert v._arch_select("amd64", "arm64") == "arm64"

    def test_unknown_arch_raises(self) -> None:
        with _versions_context("riscv64") as v:
            with pytest.raises(ValueError, match="Unsupported architecture"):
                v._arch_select("amd64", "arm64")


class TestReleaseCurlArgs:
    URL = "https://github.com/o/r/releases/download/v1/tool.tar.gz"

    def test_pins_reachable_release_asset_address(self) -> None:
        with (
            patch("nullforge.smithy.versions.reachable_address", return_value="1.2.3.4"),
            patch("nullforge.smithy.versions.curl_args", return_value={"--retry": "3"}) as args,
        ):
            assert Versions.release_curl_args(self.URL) == {"--retry": "3"}
        args.assert_called_once_with(self.URL, resolve=f"{RELEASE_ASSET_HOST}:443:1.2.3.4")

    def test_unpinned_when_no_address_reachable(self) -> None:
        with (
            patch("nullforge.smithy.versions.reachable_address", return_value=None),
            patch("nullforge.smithy.versions.curl_args", return_value={"--retry": "3"}) as args,
        ):
            Versions.release_curl_args(self.URL)
        args.assert_called_once_with(self.URL, resolve=None)


class TestVersionsUrls:
    def test_cloudflared_url_amd64_on_x86(self) -> None:
        with _versions_context("x86_64") as v:
            url = v.cloudflared_url()
        assert "amd64" in url

    def test_cloudflared_url_arm64_on_arm(self) -> None:
        with _versions_context("arm64") as v:
            url = v.cloudflared_url()
        assert "arm64" in url

    def test_telemt_tar_arch_selection(self) -> None:
        with _versions_context("x86_64") as v:
            assert "telemt-x86_64-linux-gnu.tar.gz" in v.telemt_tar()
        with _versions_context("arm64") as v:
            assert "telemt-aarch64-linux-gnu.tar.gz" in v.telemt_tar()

    def test_telemt_tar_latest_uses_latest_path(self) -> None:
        with _versions_context(overrides={"versions": {"telemt": "latest"}}) as v:
            url = v.telemt_tar()
        assert "/releases/latest/download/" in url

    def test_nvim_x86_is_appimage(self) -> None:
        with _versions_context("x86_64") as v:
            url = v.nvim_appimage()
        assert url.endswith(".appimage")

    def test_nvim_arm64_is_tar_gz(self) -> None:
        with _versions_context("arm64") as v:
            url = v.nvim_appimage()
        assert url.endswith(".tar.gz")


@contextmanager
def _pin_check_context(
    *,
    file_exists: bool = True,
    command_output: str | None = None,
    marker_lines: list[str] | None = None,
    overrides: dict | None = None,
) -> Generator[MagicMock]:
    host = MagicMock()
    host.data = _FakeData(overrides)

    def _get_fact(fact: object, *args: object, **kwargs: object) -> object:
        name = getattr(fact, "__name__", "")
        if name == "File":
            return {"mode": "755"} if file_exists else None
        if name == "Command":
            return command_output
        if name == "FileContents":
            return marker_lines
        raise AssertionError(f"unexpected fact: {fact}")

    host.get_fact.side_effect = _get_fact
    with patch("nullforge.smithy.versions._ctx_host", host):
        yield host


class TestIsPinnedVersionInstalled:
    def test_missing_binary_needs_install(self) -> None:
        with _pin_check_context(file_exists=False):
            assert is_pinned_version_installed("tmux", "/usr/local/bin/tmux") is False

    def test_matching_version_output(self) -> None:
        with _pin_check_context(command_output=f"tmux {DEFAULT_VERSIONS['tmux']}"):
            assert is_pinned_version_installed("tmux", "/usr/local/bin/tmux") is True

    def test_mismatched_version_needs_reinstall(self) -> None:
        with _pin_check_context(command_output="tmux 3.0a"):
            assert is_pinned_version_installed("tmux", "/usr/local/bin/tmux") is False

    def test_empty_version_output_needs_reinstall(self) -> None:
        with _pin_check_context(command_output=None):
            assert is_pinned_version_installed("eza", "/usr/local/bin/eza") is False

    def test_uses_tool_specific_command(self) -> None:
        with _pin_check_context(command_output=f"tmux {DEFAULT_VERSIONS['tmux']}") as host:
            is_pinned_version_installed("tmux", "/usr/local/bin/tmux")
        commands = [
            call.args[1] for call in host.get_fact.call_args_list if getattr(call.args[0], "__name__", "") == "Command"
        ]
        assert commands == ["/usr/local/bin/tmux -V 2>&1 || true"]

    def test_latest_pin_skips_version_check(self) -> None:
        with _pin_check_context(overrides={"versions": {"direnv": "latest"}}) as host:
            assert is_pinned_version_installed("direnv", "/usr/local/bin/direnv") is True
        assert all(getattr(call.args[0], "__name__", "") == "File" for call in host.get_fact.call_args_list)

    def test_marker_tool_matches_recorded_version(self) -> None:
        with _pin_check_context(marker_lines=[DEFAULT_VERSIONS["wgcf"]]):
            assert is_pinned_version_installed("wgcf", "/usr/local/bin/wgcf") is True

    def test_marker_tool_missing_marker_needs_reinstall(self) -> None:
        with _pin_check_context(marker_lines=None):
            assert is_pinned_version_installed("wgcf", "/usr/local/bin/wgcf") is False

    def test_marker_tool_outdated_marker_needs_reinstall(self) -> None:
        with _pin_check_context(marker_lines=["0.0.1"]):
            assert is_pinned_version_installed("wgcf", "/usr/local/bin/wgcf") is False


class TestRecordInstalledVersion:
    def test_writes_marker_file(self) -> None:
        with _pin_check_context():
            with patch("nullforge.smithy.versions.files") as files_mock:
                record_installed_version("wgcf")

        kwargs = files_mock.put.call_args.kwargs
        assert kwargs["dest"] == f"{VERSION_MARKER_DIR}/wgcf"
        assert kwargs["src"].getvalue() == f"{DEFAULT_VERSIONS['wgcf']}\n"
