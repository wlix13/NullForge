from pathlib import Path

import click
import pytest

from nullforge.cli.types import (
    InventoryType,
    KeyValueType,
    RuneType,
    ShellType,
    complete_paths,
)
from nullforge.runes import RUNES_DIR


CTX = click.Context(click.Command("cast"))
PARAM = click.Option(["-x"])


class TestInventoryType:
    def test_existing_file_resolves_to_absolute(self, tmp_path: Path) -> None:
        inventory = tmp_path / "inv.py"
        inventory.write_text("hosts = []\n")

        result = InventoryType().convert(str(inventory), None, None)

        assert Path(result) == inventory.resolve()

    @pytest.mark.parametrize("spec", ["@local", "host1,host2", "203.0.113.10"])
    def test_raw_host_spec_passes_through(self, spec: str) -> None:
        assert InventoryType().convert(spec, None, None) == spec

    def test_missing_path_fails(self) -> None:
        with pytest.raises(click.UsageError):
            InventoryType().convert("missing/inv.py", None, None)

    def test_shell_complete_offers_local(self) -> None:
        items = InventoryType().shell_complete(CTX, PARAM, "@l")
        assert [item.value for item in items] == ["@local"]


class TestRuneType:
    def test_builtin_name_resolves(self) -> None:
        assert RuneType().convert("warp", None, None) == RUNES_DIR / "warp.py"

    def test_custom_file_resolves(self, tmp_path: Path) -> None:
        rune = tmp_path / "custom.py"
        rune.write_text('"""Custom rune."""\n')

        assert RuneType().convert(str(rune), None, None) == rune.resolve()

    @pytest.mark.parametrize("value", ["nope", "_private", "./gone.py"])
    def test_invalid_values_fail(self, value: str) -> None:
        with pytest.raises(click.UsageError):
            RuneType().convert(value, None, None)

    def test_unknown_rune_error_lists_builtins(self) -> None:
        with pytest.raises(click.UsageError, match="warp"):
            RuneType().convert("nope", None, None)

    def test_shell_complete_returns_names_with_summaries(self) -> None:
        items = RuneType().shell_complete(CTX, PARAM, "wa")

        assert [item.value for item in items] == ["warp"]
        assert items[0].help, "Expected the rune docstring summary as completion help"

    def test_shell_complete_paths_when_path_like(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        (tmp_path / "sub").mkdir()
        (tmp_path / "sub" / "my_rune.py").write_text('"""My rune."""\n')
        monkeypatch.chdir(tmp_path)

        items = RuneType().shell_complete(CTX, PARAM, "sub/")

        assert [item.value for item in items] == ["sub/my_rune.py"]


class TestCompletePaths:
    @pytest.fixture
    def tree(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
        (tmp_path / "sub").mkdir()
        (tmp_path / "sub" / "inner.py").write_text("")
        (tmp_path / "alpha.py").write_text("")
        (tmp_path / "notes.txt").write_text("")
        monkeypatch.chdir(tmp_path)
        return tmp_path

    def test_lists_directories_first_and_filters_suffix(self, tree: Path) -> None:
        values = [item.value for item in complete_paths("")]
        assert values == ["sub/", "alpha.py"]

    def test_forward_slash_separator_preserved(self, tree: Path) -> None:
        values = [item.value for item in complete_paths("sub/")]
        assert values == ["sub/inner.py"]

    def test_backslash_separator_preserved(self, tree: Path) -> None:
        values = [item.value for item in complete_paths("sub\\")]
        assert values == ["sub\\inner.py"]

    def test_fragment_filters_entries(self, tree: Path) -> None:
        values = [item.value for item in complete_paths("al")]
        assert values == ["alpha.py"]

    def test_missing_directory_returns_empty(self, tree: Path) -> None:
        assert complete_paths("gone/") == []


class TestShellType:
    @pytest.mark.parametrize(
        ("value", "expected"), [("bash", "bash"), ("PowerShell", "powershell"), ("pwsh", "powershell")]
    )
    def test_convert_normalizes(self, value: str, expected: str) -> None:
        assert ShellType().convert(value, None, None) == expected

    def test_unsupported_shell_fails(self) -> None:
        with pytest.raises(click.UsageError):
            ShellType().convert("cmd", None, None)


class TestKeyValueType:
    @pytest.mark.parametrize("value", ["k=v", "k=", "key=a=b"])
    def test_valid_pairs_pass_through(self, value: str) -> None:
        assert KeyValueType().convert(value, None, None) == value

    @pytest.mark.parametrize("value", ["=v", "kv", ""])
    def test_invalid_pairs_fail(self, value: str) -> None:
        with pytest.raises(click.UsageError):
            KeyValueType().convert(value, None, None)
