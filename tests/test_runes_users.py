from unittest.mock import MagicMock, patch

from pyinfra.facts.files import File, FileContents
from pyinfra.facts.server import Users

from nullforge.models.users import Shell, UserRole
from nullforge.molds import FeaturesMold, UserMold, UsersMold
from nullforge.runes.users import (
    _configure_passwordless_sudo,
    _dedup_keys,
    _install_ssh_keys,
    _sudoers_filename,
    deploy_user_management,
)


class TestDedupKeys:
    def test_drops_blanks_and_comments(self) -> None:
        keys = ["ssh-ed25519 AAA a", "", "  ", "# a comment", "ssh-rsa BBB b"]
        assert _dedup_keys(keys) == ["ssh-ed25519 AAA a", "ssh-rsa BBB b"]

    def test_preserves_first_seen_order_across_duplicates(self) -> None:
        keys = ["key-a", "key-b", "key-a", "key-c", "key-b"]
        assert _dedup_keys(keys) == ["key-a", "key-b", "key-c"]

    def test_strips_surrounding_whitespace(self) -> None:
        assert _dedup_keys(["  ssh-ed25519 AAA a  "]) == ["ssh-ed25519 AAA a"]


class TestInstallSshKeys:
    def test_github_keys_installed(self) -> None:
        opts = UserMold(name="core", copy_root_keys=False, fetch_key_from_github="octocat")

        fake_host = MagicMock()
        fake_host.get_fact.return_value = "/home/core"
        fake_server = MagicMock()

        with (
            patch("nullforge.runes.users.fetch_github_keys", return_value=["ssh-ed25519 GOOD octocat"]),
            patch("nullforge.runes.users.host", fake_host),
            patch("nullforge.runes.users.server", fake_server),
            patch("nullforge.runes.users.files", MagicMock()),
        ):
            _install_ssh_keys(opts)

        fake_server.user_authorized_keys.assert_called_once()
        assert fake_server.user_authorized_keys.call_args.kwargs["public_keys"] == ["ssh-ed25519 GOOD octocat"]

    def test_github_unavailable_keeps_root_keys(self) -> None:
        opts = UserMold(name="core", copy_root_keys=True, fetch_key_from_github="bad")

        def _get_fact(fact, *args, **kwargs):
            if fact is FileContents:
                return ["ssh-rsa ROOT root"]
            return "/home/core"

        fake_host = MagicMock()
        fake_host.get_fact.side_effect = _get_fact
        fake_server = MagicMock()

        with (
            patch("nullforge.runes.users.fetch_github_keys", return_value=[]),
            patch("nullforge.runes.users.host", fake_host),
            patch("nullforge.runes.users.server", fake_server),
            patch("nullforge.runes.users.files", MagicMock()),
        ):
            _install_ssh_keys(opts)

        fake_server.user_authorized_keys.assert_called_once()
        assert fake_server.user_authorized_keys.call_args.kwargs["public_keys"] == ["ssh-rsa ROOT root"]

    def test_merges_ssh_keys_and_github_keys(self) -> None:
        opts = UserMold(
            name="ci",
            role=UserRole.DEPLOY,
            sudo_commands=["/usr/bin/systemctl restart app.service"],
            ssh_keys=["ssh-ed25519 AAA literal", "ssh-ed25519 DUP shared"],
            fetch_key_from_github="octocat",
        )

        fake_host = MagicMock()
        fake_host.get_fact.return_value = "/home/ci"
        fake_server = MagicMock()

        with (
            patch(
                "nullforge.runes.users.fetch_github_keys",
                return_value=["ssh-ed25519 DUP shared", "ssh-ed25519 BBB github"],
            ),
            patch("nullforge.runes.users.host", fake_host),
            patch("nullforge.runes.users.server", fake_server),
            patch("nullforge.runes.users.files", MagicMock()),
        ):
            _install_ssh_keys(opts)

        fake_server.user_authorized_keys.assert_called_once()
        assert fake_server.user_authorized_keys.call_args.kwargs["public_keys"] == [
            "ssh-ed25519 AAA literal",
            "ssh-ed25519 DUP shared",
            "ssh-ed25519 BBB github",
        ]

    def test_skips_root_keys_by_default(self) -> None:
        opts = UserMold(
            name="ci",
            ssh_keys=["ssh-ed25519 AAA literal"],
        )

        fake_host = MagicMock()
        fake_host.get_fact.return_value = "/home/ci"
        fake_server = MagicMock()

        with (
            patch("nullforge.runes.users.host", fake_host),
            patch("nullforge.runes.users.server", fake_server),
            patch("nullforge.runes.users.files", MagicMock()),
        ):
            _install_ssh_keys(opts)

        assert not any(call.args[0] is FileContents for call in fake_host.get_fact.call_args_list)


class TestSudoersFilename:
    def test_sanitizes_dots_for_sudoers_d(self) -> None:
        assert _sudoers_filename("alice.ops") == "alice_ops"
        assert _sudoers_filename("ci-deploy_1") == "ci-deploy_1"

    def test_sudoers_dropin_uses_sanitized_filename(self) -> None:
        fake_files = MagicMock()
        with patch("nullforge.runes.users.files", fake_files):
            _configure_passwordless_sudo(UserMold(name="alice.ops"))

        kwargs = fake_files.put.call_args.kwargs
        assert kwargs["dest"] == "/etc/sudoers.d/alice_ops"
        assert kwargs["src"].getvalue() == "alice.ops ALL=(ALL) NOPASSWD:ALL\n"


def _run_deploy(
    users_opts: UsersMold,
    *,
    is_debian_based: bool = True,
    existing_files: set[str] | None = None,
) -> tuple[MagicMock, MagicMock]:
    present_files = existing_files or set()

    def _get_fact(fact, *args, **kwargs):
        if fact is File:
            path = args[0] if args else kwargs.get("path")
            return {"mode": "0440"} if path in present_files else None
        return "/home/test"

    fake_host = MagicMock()
    fake_host.data.features = FeaturesMold(users=users_opts)
    fake_host.loop.side_effect = lambda items: items
    fake_host.get_fact.side_effect = _get_fact

    fake_pm = MagicMock()
    fake_pm.is_debian_based = is_debian_based

    fake_server = MagicMock()
    fake_files = MagicMock()

    with (
        patch("nullforge.runes.users.host", fake_host),
        patch("nullforge.runes.users.get_pm", return_value=fake_pm),
        patch("nullforge.runes.users.server", fake_server),
        patch("nullforge.runes.users.files", fake_files),
        patch("nullforge.runes.users.fetch_github_keys", return_value=[]),
    ):
        deploy_user_management()

    return fake_server, fake_files


class TestDeployUserManagement:
    def test_admin_user_default_behavior(self) -> None:
        opts = UsersMold(
            users=[
                UserMold(
                    name="ops",
                    role=UserRole.ADMIN,
                    copy_root_keys=False,
                    shell=Shell.ZSH,
                    set_root_shell_like_user=True,
                )
            ]
        )
        fake_server, fake_files = _run_deploy(opts, is_debian_based=True)

        user_calls = fake_server.user.call_args_list
        assert len(user_calls) == 2
        assert user_calls[0].kwargs["user"] == "ops"
        assert user_calls[0].kwargs["groups"] == ["sudo"]
        assert user_calls[0].kwargs["append"] is True
        assert user_calls[1].kwargs["user"] == "root"
        assert user_calls[1].kwargs["shell"] == "/bin/zsh"

        fake_files.put.assert_called_once()
        assert fake_files.put.call_args.kwargs["dest"] == "/etc/sudoers.d/ops"
        assert fake_files.put.call_args.kwargs["src"].getvalue() == "ops ALL=(ALL) NOPASSWD:ALL\n"

    def test_admin_user_with_password_removes_dropin(self) -> None:
        opts = UsersMold(
            users=[
                UserMold(
                    name="main.adm",
                    role=UserRole.ADMIN,
                    password="main-secret",
                    copy_root_keys=False,
                )
            ]
        )
        _, fake_files = _run_deploy(
            opts,
            existing_files={"/etc/sudoers.d/main_adm"},
        )

        removed = [
            call.kwargs["path"] for call in fake_files.file.call_args_list if call.kwargs.get("present") is False
        ]
        assert removed == ["/etc/sudoers.d/main_adm"]
        assert all(call.kwargs["_sudo"] is True for call in fake_files.file.call_args_list)

    def test_per_role_groups_and_sudoers(self) -> None:
        opts = UsersMold(
            users=[
                UserMold(name="adm", role=UserRole.ADMIN),
                UserMold(name="adm-pw", role=UserRole.ADMIN, password="secret-admin"),
                UserMold(
                    name="ci",
                    role=UserRole.DEPLOY,
                    sudo_commands=["/usr/bin/systemctl restart app.service", "/usr/bin/podman ps"],
                ),
                UserMold(
                    name="ci-pw",
                    role=UserRole.DEPLOY,
                    password="secret-deploy",
                    sudo_commands=["/usr/bin/systemctl reload nginx"],
                ),
                UserMold(name="viewer", role=UserRole.NONE),
            ]
        )
        fake_server, fake_files = _run_deploy(opts, is_debian_based=False)

        groups_by_user = {call.kwargs["user"]: call.kwargs["groups"] for call in fake_server.user.call_args_list}
        append_by_user = {call.kwargs["user"]: call.kwargs["append"] for call in fake_server.user.call_args_list}
        assert groups_by_user == {
            "adm": ["wheel"],
            "adm-pw": ["wheel"],
            "ci": [],
            "ci-pw": [],
            "viewer": [],
        }
        assert append_by_user == {
            "adm": True,
            "adm-pw": True,
            "ci": False,
            "ci-pw": False,
            "viewer": False,
        }

        puts_by_dest = {call.kwargs["dest"]: call.kwargs["src"].getvalue() for call in fake_files.put.call_args_list}
        assert puts_by_dest["/etc/sudoers.d/adm"] == "adm ALL=(ALL) NOPASSWD:ALL\n"
        assert "/etc/sudoers.d/adm-pw" not in puts_by_dest
        assert puts_by_dest["/root/.nullforge-chpasswd-adm-pw"] == "adm-pw:secret-admin\n"
        assert (
            puts_by_dest["/etc/sudoers.d/ci"]
            == "ci ALL=(ALL) NOPASSWD: /usr/bin/systemctl restart app.service, /usr/bin/podman ps\n"
        )
        assert puts_by_dest["/etc/sudoers.d/ci-pw"] == "ci-pw ALL=(ALL) NOPASSWD: /usr/bin/systemctl reload nginx\n"
        assert "/etc/sudoers.d/viewer" not in puts_by_dest
        fake_files.file.assert_not_called()

    def test_removes_sudoers_dropin_when_admin_password_set_or_role_none(self) -> None:
        opts = UsersMold(
            users=[
                UserMold(name="main.adm", role=UserRole.ADMIN, password="main-secret", copy_root_keys=False),
                UserMold(name="adm-pw", role=UserRole.ADMIN, password="adm-secret"),
                UserMold(name="viewer", role=UserRole.NONE),
                UserMold(
                    name="ci",
                    role=UserRole.DEPLOY,
                    password="ci-secret",
                    sudo_commands=["/usr/bin/systemctl reload nginx"],
                ),
            ]
        )
        _, fake_files = _run_deploy(
            opts,
            existing_files={
                "/etc/sudoers.d/main_adm",
                "/etc/sudoers.d/adm-pw",
                "/etc/sudoers.d/viewer",
                "/etc/sudoers.d/ci",
            },
        )

        removed = [
            call.kwargs["path"] for call in fake_files.file.call_args_list if call.kwargs.get("present") is False
        ]
        assert removed == [
            "/etc/sudoers.d/main_adm",
            "/etc/sudoers.d/adm-pw",
            "/etc/sudoers.d/viewer",
        ]
        assert all(call.kwargs["_sudo"] is True for call in fake_files.file.call_args_list)

    def test_skips_dropin_removal_when_file_absent(self) -> None:
        opts = UsersMold(
            users=[
                UserMold(name="ops", role=UserRole.ADMIN, password="secret", copy_root_keys=False),
                UserMold(name="viewer", role=UserRole.NONE),
            ]
        )
        _, fake_files = _run_deploy(opts, existing_files=set())
        fake_files.file.assert_not_called()

    def test_root_shell_sync_when_set_root_shell_like_user(self) -> None:
        opts = UsersMold(
            users=[
                UserMold(
                    name="ops",
                    role=UserRole.ADMIN,
                    shell=Shell.ZSH,
                    set_root_shell_like_user=True,
                ),
                UserMold(
                    name="admin2",
                    role=UserRole.ADMIN,
                    shell=Shell.BASH,
                    set_root_shell_like_user=True,
                ),
            ]
        )
        fake_server, _ = _run_deploy(opts, is_debian_based=True)

        root_shell_calls = [call for call in fake_server.user.call_args_list if call.kwargs["user"] == "root"]
        # root shell set to last user's shell (BASH)
        assert len(root_shell_calls) == 2
        assert root_shell_calls[-1].kwargs["shell"] == "/bin/bash"


class TestGroupStrippingOnRoleDowngrade:
    def _run_deploy_with_users_fact(
        self,
        users_opts: UsersMold,
        *,
        is_debian_based: bool = True,
        users_fact: dict | None = None,
    ) -> tuple[MagicMock, MagicMock, MagicMock]:
        present_files = set()

        def _get_fact(fact, *args, **kwargs):
            if fact is File:
                path = args[0] if args else kwargs.get("path")
                return {"mode": "0440"} if path in present_files else None
            if fact is Users:
                return users_fact or {}
            return "/home/test"

        fake_host = MagicMock()
        fake_host.data.features = FeaturesMold(users=users_opts)
        fake_host.loop.side_effect = lambda items: items
        fake_host.get_fact.side_effect = _get_fact

        fake_pm = MagicMock()
        fake_pm.is_debian_based = is_debian_based

        fake_server = MagicMock()
        fake_files = MagicMock()

        with (
            patch("nullforge.runes.users.host", fake_host),
            patch("nullforge.runes.users.get_pm", return_value=fake_pm),
            patch("nullforge.runes.users.server", fake_server),
            patch("nullforge.runes.users.files", fake_files),
            patch("nullforge.runes.users.fetch_github_keys", return_value=[]),
        ):
            deploy_user_management()

        return fake_server, fake_files, fake_host

    def test_deploy_user_in_sudo_group_strips_group_debian(self) -> None:
        opts = UsersMold(
            users=[
                UserMold(
                    name="ci",
                    role=UserRole.DEPLOY,
                    sudo_commands=["/usr/bin/systemctl restart app.service"],
                )
            ]
        )
        fake_server, _, _ = self._run_deploy_with_users_fact(
            opts,
            is_debian_based=True,
            users_fact={"ci": {"groups": ["sudo", "docker"]}},
        )

        shell_calls = fake_server.shell.call_args_list
        gpasswd_calls = [call for call in shell_calls if "gpasswd -d" in call.kwargs["commands"][0]]
        assert len(gpasswd_calls) == 1
        assert gpasswd_calls[0].kwargs["commands"][0] == "gpasswd -d ci sudo"
        assert gpasswd_calls[0].kwargs["_sudo"] is True

    def test_deploy_user_in_wheel_group_strips_group_rhel(self) -> None:
        opts = UsersMold(
            users=[
                UserMold(
                    name="ci",
                    role=UserRole.DEPLOY,
                    sudo_commands=["/usr/bin/systemctl restart app.service"],
                )
            ]
        )
        fake_server, _, _ = self._run_deploy_with_users_fact(
            opts,
            is_debian_based=False,
            users_fact={"ci": {"groups": ["wheel", "docker"]}},
        )

        shell_calls = fake_server.shell.call_args_list
        gpasswd_calls = [call for call in shell_calls if "gpasswd -d" in call.kwargs["commands"][0]]
        assert len(gpasswd_calls) == 1
        assert gpasswd_calls[0].kwargs["commands"][0] == "gpasswd -d ci wheel"
        assert gpasswd_calls[0].kwargs["_sudo"] is True

    def test_none_user_not_in_sudo_group_no_shell_call(self) -> None:
        opts = UsersMold(users=[UserMold(name="viewer", role=UserRole.NONE)])
        fake_server, _, _ = self._run_deploy_with_users_fact(
            opts,
            is_debian_based=True,
            users_fact={"viewer": {"groups": ["docker"]}},
        )

        shell_calls = fake_server.shell.call_args_list
        gpasswd_calls = [call for call in shell_calls if "gpasswd -d" in call.kwargs["commands"][0]]
        assert len(gpasswd_calls) == 0

    def test_admin_user_no_gpasswd_call(self) -> None:
        opts = UsersMold(
            users=[
                UserMold(
                    name="ops",
                    role=UserRole.ADMIN,
                    copy_root_keys=False,
                    shell=Shell.ZSH,
                )
            ]
        )
        fake_server, _, _ = self._run_deploy_with_users_fact(
            opts,
            is_debian_based=True,
            users_fact={"ops": {"groups": ["sudo", "docker"]}},
        )

        shell_calls = fake_server.shell.call_args_list
        gpasswd_calls = [call for call in shell_calls if "gpasswd -d" in call.kwargs["commands"][0]]
        assert len(gpasswd_calls) == 0
