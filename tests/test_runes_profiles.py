from unittest.mock import MagicMock, patch

from nullforge.models.profiles import NerdFont
from nullforge.runes.profiles import ZSHRC_MARKER, _configure_user_zshrc, _install_nerd_font
from nullforge.smithy.versions import DEFAULT_VERSIONS, Versions


def _configure(block_fact: object) -> MagicMock:
    """Run the .zshrc helper against a given `Block` fact, returning the files operations mock."""

    fake_host = MagicMock()
    fake_host.get_fact.return_value = block_fact
    fake_files = MagicMock()

    with (
        patch("nullforge.runes.profiles.host", fake_host),
        patch("nullforge.runes.profiles.files", fake_files),
    ):
        _configure_user_zshrc("core", "/home/core")

    return fake_files


class TestZshrcMarker:
    def test_marker_has_no_regex_metacharacters(self) -> None:
        # the Block fact interpolates the marker straight into an awk regex
        assert not set(ZSHRC_MARKER.replace("{mark}", "")) & set(".*+?[]()^$|\\/")


class TestConfigureUserZshrc:
    def test_block_written_with_marker(self) -> None:
        files_mock = _configure(["export ZSH=/home/core/.oh-my-zsh"])

        kwargs = files_mock.block.call_args.kwargs
        assert kwargs["path"] == "/home/core/.zshrc"
        assert kwargs["marker"] == ZSHRC_MARKER

    def test_block_is_prepended(self) -> None:
        files_mock = _configure(None)

        kwargs = files_mock.block.call_args.kwargs
        # both true means prepend, so host-specific lines land after ours and win
        assert kwargs["before"] is True
        assert kwargs["after"] is True

    def test_content_rendered_for_home(self) -> None:
        files_mock = _configure(None)

        content = files_mock.block.call_args.kwargs["content"]
        assert 'export ZSH="/home/core/.oh-my-zsh"' in content
        assert not content.endswith("\n")

    def test_unmarked_zshrc_is_cleared_with_a_backup(self) -> None:
        files_mock = _configure([])

        kwargs = files_mock.line.call_args.kwargs
        assert kwargs["path"] == "/home/core/.zshrc"
        assert kwargs["line"] == ".*"
        assert kwargs["present"] is False
        assert kwargs["backup"] is True

    def test_marked_zshrc_is_left_alone(self) -> None:
        files_mock = _configure(["export ZSH=/home/core/.oh-my-zsh"])

        files_mock.line.assert_not_called()

    def test_missing_zshrc_is_left_alone(self) -> None:
        files_mock = _configure(None)

        files_mock.line.assert_not_called()


def _install_font(*, already_installed: bool, family: NerdFont = NerdFont.FIRA_CODE) -> tuple[MagicMock, MagicMock]:
    """Run the font helper against a given `Directory` fact, returning the files/server mocks."""

    fake_host = MagicMock()
    fake_host.get_fact.return_value = already_installed
    fake_files = MagicMock()
    fake_server = MagicMock()

    with (
        patch("nullforge.runes.profiles.host", fake_host),
        patch("nullforge.runes.profiles.files", fake_files),
        patch("nullforge.runes.profiles.server", fake_server),
        patch("nullforge.runes.profiles.sha256_for_download_url", return_value="deadbeef"),
        patch("nullforge.runes.profiles.get_versions", return_value=Versions({})),
    ):
        _install_nerd_font("core", "/home/core", family)

    return fake_files, fake_server


class TestInstallNerdFont:
    def test_skipped_when_already_installed(self) -> None:
        files_mock, server_mock = _install_font(already_installed=True)

        files_mock.download.assert_not_called()
        server_mock.shell.assert_not_called()

    def test_archive_downloaded_for_named_family(self) -> None:
        files_mock, _ = _install_font(already_installed=False, family=NerdFont.JETBRAINS_MONO)

        kwargs = files_mock.download.call_args.kwargs
        assert kwargs["src"].endswith("/JetBrainsMono.tar.xz")
        assert kwargs["sha256sum"] == "deadbeef"

    def test_install_dir_is_version_pinned(self) -> None:
        _, server_mock = _install_font(already_installed=False)

        version = DEFAULT_VERSIONS["nerd_fonts"]
        commands = server_mock.shell.call_args.kwargs["commands"]
        assert any(f"/home/core/.local/share/fonts/FiraCode-{version}" in cmd for cmd in commands)
        # older versions of the same family are cleared so the two never mix
        assert commands[0] == "rm -rf /home/core/.local/share/fonts/FiraCode-*"
