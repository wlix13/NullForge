"""Foundry component and CLI commands."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import rich_click as click

from nullforge.cli.core import BaseComponent
from nullforge.cli.types import InventoryType, KeyValueType, RuneType

from .controller import CastOptions, FoundryController


if TYPE_CHECKING:
    from pathlib import Path

    from nullforge.cli.app import NullForgeCli


class FoundryComponent(BaseComponent["NullForgeCli", FoundryController]):
    name = "foundry"
    controller_class = FoundryController
    expose_controller = True

    @classmethod
    def expose_cli(cls, base: click.Group) -> None:
        @base.command("cast", context_settings={"ignore_unknown_options": True})
        @click.option(
            "-i",
            "--inventory",
            required=True,
            type=InventoryType(),
            help="Inventory .py file or raw host spec (e.g. @local, host1,host2).",
        )
        @click.option(
            "-r",
            "--rune",
            "runes",
            multiple=True,
            type=RuneType(),
            help="Built-in rune name or path to a custom rune file; repeatable, runs in order. "
            "Omit to run the full cast.",
        )
        @click.option(
            "--with-prepare",
            is_flag=True,
            help="Run the prepare rune as a separate first deploy (for fresh hosts without sudo).",
        )
        @click.option(
            "--dry",
            is_flag=True,
            help="Don't execute operations on the target hosts.",
        )
        @click.option(
            "--diff",
            is_flag=True,
            help="Show file and template differences.",
        )
        @click.option(
            "-y",
            "--yes",
            is_flag=True,
            help="Execute operations without prompting.",
        )
        @click.option(
            "--debug",
            is_flag=True,
            help="Print Pyinfra debug logs.",
        )
        @click.option(
            "-v",
            "verbosity",
            count=True,
            help="Print meta (-v), input (-vv) and output (-vvv).",
        )
        @click.option(
            "--ssh-user",
            help="SSH user to connect as.",
        )
        @click.option(
            "--ssh-port",
            type=int,
            help="SSH port to connect to.",
        )
        @click.option(
            "--ssh-key",
            help="SSH private key file.",
        )
        @click.option(
            "--ssh-key-password",
            help="SSH private key password.",
        )
        @click.option(
            "--ssh-password",
            help="SSH password.",
        )
        @click.option(
            "--sudo-user",
            help="User to sudo as.",
        )
        @click.option(
            "--parallel",
            type=int,
            help="Number of hosts to run in parallel.",
        )
        @click.option(
            "--limit",
            multiple=True,
            help="Restrict target hosts by name or group.",
        )
        @click.option(
            "--data",
            multiple=True,
            type=KeyValueType(),
            help="Override target data (key=value).",
        )
        @click.argument(
            "pyinfra_args",
            nargs=-1,
            type=click.UNPROCESSED,
        )
        @click.pass_obj
        def cast(
            app: NullForgeCli,
            inventory: str,
            runes: tuple[Path, ...],
            with_prepare: bool,
            pyinfra_args: tuple[str, ...],
            **proxied: Any,
        ) -> None:
            """Cast runes onto the inventory via Pyinfra.

            Unknown options are passed through to Pyinfra.
            """

            app.foundry.cast(inventory, runes, with_prepare, CastOptions(extra=pyinfra_args, **proxied))
