from unittest.mock import MagicMock, patch

from pyinfra.facts.files import FileContents
from pyinfra.facts.server import Users

from nullforge.models.containers import ContainersBackendType
from nullforge.models.users import UserRole
from nullforge.molds import ContainersMold, FeaturesMold, UserMold, UsersMold
from nullforge.runes.containers import SUBID_COUNT, SUBID_MIN, deploy_containers


def _mixed_users() -> UsersMold:
    return UsersMold(
        users=[
            UserMold(name="core", role=UserRole.ADMIN),
            UserMold(name="ops2", role=UserRole.ADMIN),
            UserMold(
                name="ci",
                role=UserRole.DEPLOY,
                sudo_commands=["/usr/bin/systemctl restart app.service"],
            ),
            UserMold(name="viewer", role=UserRole.NONE),
        ]
    )


class TestDeployContainersAdminFilter:
    def test_docker_adds_only_admin_users(self) -> None:
        features = FeaturesMold(
            users=_mixed_users(),
            containers=ContainersMold(
                install=True,
                backend_type=ContainersBackendType.DOCKER,
                skopeo=False,
            ),
        )
        fake_host = MagicMock()
        fake_host.data.features = features
        fake_host.loop.side_effect = lambda items: items
        fake_server = MagicMock()

        with (
            patch("nullforge.runes.containers.host", fake_host),
            patch("nullforge.runes.containers.server", fake_server),
            patch("nullforge.runes.containers._install_docker"),
            patch("nullforge.runes.containers._install_gvisor"),
        ):
            deploy_containers()

        added = [call.kwargs["user"] for call in fake_server.user.call_args_list]
        assert added == ["core", "ops2"]

    def test_podman_subids_and_autoupdate_only_for_admin_users(self) -> None:
        features = FeaturesMold(
            users=_mixed_users(),
            containers=ContainersMold(
                install=True,
                backend_type=ContainersBackendType.PODMAN,
                skopeo=False,
            ),
        )

        def _get_fact(fact, *args, **kwargs):
            if fact is Users:
                return {
                    "core": {},
                    "ops2": {},
                    "ci": {},
                    "viewer": {},
                }
            if fact is FileContents:
                return []
            return None

        fake_host = MagicMock()
        fake_host.data.features = features
        fake_host.loop.side_effect = lambda items: items
        fake_host.get_fact.side_effect = _get_fact
        fake_files = MagicMock()
        fake_server = MagicMock()
        fake_systemd = MagicMock()

        with (
            patch("nullforge.runes.containers.host", fake_host),
            patch("nullforge.runes.containers.files", fake_files),
            patch("nullforge.runes.containers.server", fake_server),
            patch("nullforge.runes.containers.systemd", fake_systemd),
            patch("nullforge.runes.containers._install_crun"),
            patch("nullforge.runes.containers._install_podman"),
        ):
            deploy_containers()

        subid_lines = [(call.kwargs["path"], call.kwargs["replace"]) for call in fake_files.line.call_args_list]
        second_start = SUBID_MIN + SUBID_COUNT
        assert subid_lines == [
            ("/etc/subuid", f"core:{SUBID_MIN}:{SUBID_COUNT}"),
            ("/etc/subuid", f"ops2:{second_start}:{SUBID_COUNT}"),
            ("/etc/subgid", f"core:{SUBID_MIN}:{SUBID_COUNT}"),
            ("/etc/subgid", f"ops2:{second_start}:{SUBID_COUNT}"),
        ]

        linger_cmds = [call.kwargs["commands"][0] for call in fake_server.shell.call_args_list]
        assert linger_cmds == [
            "loginctl enable-linger core",
            "loginctl enable-linger ops2",
        ]


def test_empty_users_list_no_admin_users() -> None:
    features = FeaturesMold(
        users=UsersMold(),
        containers=ContainersMold(
            install=True,
            backend_type=ContainersBackendType.DOCKER,
            skopeo=False,
        ),
    )
    fake_host = MagicMock()
    fake_host.data.features = features
    fake_host.loop.side_effect = lambda items: items
    fake_server = MagicMock()

    with (
        patch("nullforge.runes.containers.host", fake_host),
        patch("nullforge.runes.containers.server", fake_server),
        patch("nullforge.runes.containers._install_docker"),
        patch("nullforge.runes.containers._install_gvisor"),
    ):
        deploy_containers()

    added = [call.kwargs["user"] for call in fake_server.user.call_args_list]
    assert added == []
