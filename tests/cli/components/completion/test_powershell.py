import click
import pytest
from click.shell_completion import CompletionItem, get_completion_class

from nullforge.cli.components.completion.powershell import (
    PowerShellComplete,
    register_powershell_completion,
    split_powershell_line,
)


def _completer() -> PowerShellComplete:
    return PowerShellComplete(click.Group("nullforge"), {}, "nullforge", "_NULLFORGE_COMPLETE")


class TestSplitPowershellLine:
    def test_plain_words(self) -> None:
        assert split_powershell_line("nullforge cast -r warp") == ["nullforge", "cast", "-r", "warp"]

    def test_backslash_paths_survive(self) -> None:
        assert split_powershell_line(r"nullforge cast -r D:\runes\cu") == [
            "nullforge",
            "cast",
            "-r",
            r"D:\runes\cu",
        ]

    def test_double_quoted_word_with_spaces(self) -> None:
        assert split_powershell_line('nullforge cast -r "D:\\x y\\r.py"') == [
            "nullforge",
            "cast",
            "-r",
            "D:\\x y\\r.py",
        ]

    def test_single_quoted_word(self) -> None:
        assert split_powershell_line("nullforge cast -i 'inv file.py'") == [
            "nullforge",
            "cast",
            "-i",
            "inv file.py",
        ]

    def test_unterminated_quote(self) -> None:
        assert split_powershell_line('nullforge "abc') == ["nullforge", "abc"]


class TestGetCompletionArgs:
    def test_mid_word(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("_NULLFORGE_COMPLETE_WORDS", "nullforge cast -r wa")
        monkeypatch.setenv("_NULLFORGE_COMPLETE_INCOMPLETE", "wa")

        assert _completer().get_completion_args() == (["cast", "-r"], "wa")

    def test_trailing_space(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("_NULLFORGE_COMPLETE_WORDS", "nullforge cast -r")
        monkeypatch.setenv("_NULLFORGE_COMPLETE_INCOMPLETE", "")

        assert _completer().get_completion_args() == (["cast", "-r"], "")

    def test_windows_path_incomplete_unmangled(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("_NULLFORGE_COMPLETE_WORDS", r"nullforge cast -r D:\runes\cu")
        monkeypatch.setenv("_NULLFORGE_COMPLETE_INCOMPLETE", r"D:\runes\cu")

        assert _completer().get_completion_args() == (["cast", "-r"], r"D:\runes\cu")

    def test_missing_env_vars(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("_NULLFORGE_COMPLETE_WORDS", raising=False)
        monkeypatch.delenv("_NULLFORGE_COMPLETE_INCOMPLETE", raising=False)

        assert _completer().get_completion_args() == ([], "")


class TestFormatCompletion:
    def test_with_help(self) -> None:
        item = CompletionItem("warp", help="Cloudflare WARP deployment module.")
        assert _completer().format_completion(item) == "plain\twarp\tCloudflare WARP deployment module."

    def test_without_help(self) -> None:
        assert _completer().format_completion(CompletionItem("warp")) == "plain\twarp\t"


class TestSource:
    def test_script_registers_both_command_names(self) -> None:
        script = _completer().source()

        assert "Register-ArgumentCompleter -Native" in script
        assert '"nullforge", "nullforge.exe"' in script
        assert "_NULLFORGE_COMPLETE_WORDS" in script
        assert "_NULLFORGE_COMPLETE_INCOMPLETE" in script


def test_registered_under_both_names() -> None:
    register_powershell_completion()

    assert get_completion_class("powershell") is PowerShellComplete
    assert get_completion_class("pwsh") is PowerShellComplete
