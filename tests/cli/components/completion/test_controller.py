from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from nullforge.cli.app import NullForgeCli, cli
from nullforge.cli.components.completion.errors import ProfileNotFound, UnsupportedShell
from nullforge.cli.core.errors import Unreachable


@pytest.fixture
def exposed_app(app: NullForgeCli) -> NullForgeCli:
    app.cli_root = cli
    return app


@pytest.fixture
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    return tmp_path


class TestScript:
    def test_powershell_script(self, exposed_app: NullForgeCli) -> None:
        script = exposed_app.completion.script("powershell")

        assert "Register-ArgumentCompleter" in script
        assert "_NULLFORGE_COMPLETE" in script

    def test_zsh_script_uses_click_template(self, exposed_app: NullForgeCli) -> None:
        script = exposed_app.completion.script("zsh")

        assert "_NULLFORGE_COMPLETE" in script
        assert "nullforge" in script

    def test_unknown_shell_raises(self, exposed_app: NullForgeCli) -> None:
        with pytest.raises(UnsupportedShell):
            exposed_app.completion.script("klingon")

    def test_without_exposed_cli_raises(self, app: NullForgeCli) -> None:
        with pytest.raises(Unreachable):
            app.completion.script("powershell")


class TestInstall:
    def test_powershell_install_is_idempotent(self, exposed_app: NullForgeCli, home: Path, tmp_path: Path) -> None:
        profile = tmp_path / "profile" / "Microsoft.PowerShell_profile.ps1"
        run_result = MagicMock(returncode=0, stdout=f"{profile}\n")
        target = "nullforge.cli.components.completion.controller"

        with (
            patch(f"{target}.shutil.which", return_value="C:\\pwsh.exe"),
            patch(f"{target}.subprocess.run", return_value=run_result),
        ):
            script_path, profile_path = exposed_app.completion.install("powershell")
            exposed_app.completion.install("powershell")

        assert script_path == home / ".nullforge" / "completion.ps1"
        assert "Register-ArgumentCompleter" in script_path.read_text(encoding="utf-8")
        assert profile_path == profile
        content = profile.read_text(encoding="utf-8")
        assert content.count("# >>> nullforge completion >>>") == 1, "install must be idempotent"
        assert f'. "{script_path}"' in content

    def test_fish_install_writes_autoload_file(self, exposed_app: NullForgeCli, home: Path) -> None:
        script_path, profile_path = exposed_app.completion.install("fish")

        assert script_path == home / ".config" / "fish" / "completions" / "nullforge.fish"
        assert profile_path == script_path
        assert script_path.is_file()

    def test_powershell_missing_shell_raises(self, exposed_app: NullForgeCli, home: Path) -> None:
        target = "nullforge.cli.components.completion.controller"

        with patch(f"{target}.shutil.which", return_value=None):
            with pytest.raises(ProfileNotFound):
                exposed_app.completion.install("powershell")
