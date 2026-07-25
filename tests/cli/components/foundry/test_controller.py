import json
import sys
from unittest.mock import MagicMock, patch

import pytest

from nullforge.cli.app import NullForgeCli
from nullforge.cli.components.foundry.controller import CastOptions
from nullforge.cli.components.foundry.errors import PyinfraExecutionFailed, PyinfraLaunchFailed
from nullforge.foundry import FOUNDRY_DIR
from nullforge.runes import rune_path


RUN_TARGET = "nullforge.cli.components.foundry.controller.subprocess.run"


class TestResolveStages:
    def test_no_runes_uses_full_cast(self, app: NullForgeCli) -> None:
        assert app.foundry.resolve_stages((), False) == [(FOUNDRY_DIR / "full_cast.py", [])]

    def test_with_prepare_without_runes_bootstraps_full_cast(self, app: NullForgeCli) -> None:
        stages = app.foundry.resolve_stages((), True)

        assert stages == [
            (FOUNDRY_DIR / "cast.py", [rune_path("prepare")]),
            (FOUNDRY_DIR / "full_cast.py", []),
        ]

    def test_selected_runes_dedupe_in_order(self, app: NullForgeCli) -> None:
        warp, dns = rune_path("warp"), rune_path("dns")

        stages = app.foundry.resolve_stages((warp, dns, warp), False)

        assert stages == [(FOUNDRY_DIR / "cast.py", [warp, dns])]

    def test_with_prepare_becomes_separate_first_stage(self, app: NullForgeCli) -> None:
        warp = rune_path("warp")

        stages = app.foundry.resolve_stages((warp,), True)

        assert stages == [
            (FOUNDRY_DIR / "cast.py", [rune_path("prepare")]),
            (FOUNDRY_DIR / "cast.py", [warp]),
        ]

    def test_with_prepare_does_not_duplicate_explicit_prepare(self, app: NullForgeCli) -> None:
        prepare = rune_path("prepare")

        stages = app.foundry.resolve_stages((prepare,), True)

        assert stages == [(FOUNDRY_DIR / "cast.py", [prepare])]


class TestBuildArgv:
    def test_full_cast_argv(self, app: NullForgeCli) -> None:
        argv = app.foundry.build_argv("inv.py", FOUNDRY_DIR / "full_cast.py", [], CastOptions())

        assert argv == [
            sys.executable,
            "-m",
            "nullforge.foundry._pyinfra",
            "inv.py",
            str(FOUNDRY_DIR / "full_cast.py"),
        ]

    def test_all_option_kinds(self, app: NullForgeCli) -> None:
        warp = rune_path("warp")
        options = CastOptions(
            dry=True,
            verbosity=2,
            ssh_user="root",
            ssh_port=2222,
            limit=("a", "b"),
            data=("k=v",),
            extra=("--serial",),
        )

        argv = app.foundry.build_argv("@local", FOUNDRY_DIR / "cast.py", [warp], options)

        assert argv == [
            sys.executable,
            "-m",
            "nullforge.foundry._pyinfra",
            "@local",
            str(FOUNDRY_DIR / "cast.py"),
            "--dry",
            "-v",
            "-v",
            "--ssh-user",
            "root",
            "--ssh-port",
            "2222",
            "--limit",
            "a",
            "--limit",
            "b",
            "--data",
            "k=v",
            "--data",
            f"_nullforge_runes={json.dumps([str(warp)])}",
            "--serial",
        ]


class TestCast:
    def test_runs_pyinfra_inheriting_stdio(self, app: NullForgeCli) -> None:
        with patch(RUN_TARGET, return_value=MagicMock(returncode=0)) as run_mock:
            app.foundry.cast("@local", (rune_path("base"),), False, CastOptions())

        assert run_mock.call_count == 1
        assert run_mock.call_args.kwargs == {"check": False}, "stdio must be inherited, not captured"

    def test_nonzero_exit_raises_with_returncode(self, app: NullForgeCli) -> None:
        with patch(RUN_TARGET, return_value=MagicMock(returncode=3)):
            with pytest.raises(PyinfraExecutionFailed) as e:
                app.foundry.cast("@local", (), False, CastOptions())

        assert e.value.returncode == 3

    def test_launch_failure_raises(self, app: NullForgeCli) -> None:
        with patch(RUN_TARGET, side_effect=OSError("no python")):
            with pytest.raises(PyinfraLaunchFailed):
                app.foundry.cast("@local", (), False, CastOptions())

    def test_with_prepare_full_cast_runs_prepare_then_full_cast(self, app: NullForgeCli) -> None:
        with patch(RUN_TARGET, return_value=MagicMock(returncode=0)) as run_mock:
            app.foundry.cast("@local", (), True, CastOptions())

        assert run_mock.call_count == 2
        first_argv = run_mock.call_args_list[0].args[0]
        second_argv = run_mock.call_args_list[1].args[0]
        assert str(FOUNDRY_DIR / "cast.py") in first_argv
        assert f"_nullforge_runes={json.dumps([str(rune_path('prepare'))])}" in first_argv
        assert str(FOUNDRY_DIR / "full_cast.py") in second_argv

    def test_failed_prepare_stage_stops_the_cast(self, app: NullForgeCli) -> None:
        with patch(RUN_TARGET, return_value=MagicMock(returncode=1)) as run_mock:
            with pytest.raises(PyinfraExecutionFailed):
                app.foundry.cast("@local", (rune_path("warp"),), True, CastOptions())

        assert run_mock.call_count == 1, "the second stage must not run after a failed prepare"
