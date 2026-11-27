import pytest
from pydantic import ValidationError

from nullforge.models.users import UserRole
from nullforge.molds.base_mold import REDACTED_VALUE
from nullforge.molds.features import FeaturesMold
from nullforge.molds.user import UserMold, UsersMold


class TestFetchKeyFromGithub:
    @pytest.mark.parametrize(
        "username",
        ["octocat", "mojombo", "a"],
    )
    def test_accepts_valid_username(self, username: str) -> None:
        assert UserMold(name="test", fetch_key_from_github=username).fetch_key_from_github == username

    @pytest.mark.parametrize(
        "username",
        ["", "-octocat", "user_name", "user.name", "with space", "a" * 40],
    )
    def test_rejects_invalid_username(self, username: str) -> None:
        with pytest.raises(ValidationError):
            UserMold(name="test", fetch_key_from_github=username)


class TestUserRole:
    def test_enum_values(self) -> None:
        assert UserRole.ADMIN == "admin"
        assert UserRole.DEPLOY == "deploy"
        assert UserRole.NONE == "none"


class TestUserMold:
    def test_defaults(self) -> None:
        user = UserMold(name="viewer")
        assert user.role is UserRole.NONE
        assert user.sudo_commands is None
        assert user.ssh_keys == []
        assert user.copy_root_keys is False
        assert user.set_root_shell_like_user is False

    @pytest.mark.parametrize("name", ["root", "", "-bad", "has space", "bad/slash"])
    def test_rejects_invalid_or_root_name(self, name: str) -> None:
        with pytest.raises(ValidationError):
            UserMold(name=name)

    @pytest.mark.parametrize("name", ["ALL", ".", ".."])
    def test_rejects_sudoers_keyword_and_path_traversal(self, name: str) -> None:
        with pytest.raises(ValidationError, match="sudoers keyword or path traversal"):
            UserMold(name=name)

    @pytest.mark.parametrize("name", ["ci-deploy", "ops.team", "user_1", "a-b.c"])
    def test_accepts_valid_names(self, name: str) -> None:
        assert UserMold(name=name).name == name

    def test_deploy_requires_sudo_commands(self) -> None:
        with pytest.raises(ValidationError):
            UserMold(name="ci", role=UserRole.DEPLOY)
        with pytest.raises(ValidationError):
            UserMold(
                name="ci",
                role=UserRole.DEPLOY,
                sudo_commands=[],
            )

    @pytest.mark.parametrize("role", [UserRole.ADMIN, UserRole.NONE])
    def test_sudo_commands_rejected_for_non_deploy_roles(self, role: UserRole) -> None:
        with pytest.raises(ValidationError):
            UserMold(
                name="ops",
                role=role,
                sudo_commands=["/usr/bin/systemctl restart app"],
            )

    @pytest.mark.parametrize(
        "command",
        [
            "",
            "/",
            "ALL",
            "systemctl restart app",
            "/usr/bin/",
            "/usr/bin/ foo",
            "/usr/bin/systemctl restart app\nroot ALL=(ALL) NOPASSWD:ALL",
            "/usr/bin/systemctl restart app, /bin/sh",
            "/usr/bin/systemctl restart app; /bin/sh",
            "/usr/bin/systemctl restart app # comment",
            "/usr/bin/systemctl\nrestart",
            "/usr/bin/foo:bar",
            "/usr/bin/systemctl restart app*",
            "/usr/bin/systemctl restart app?",
            "/usr/bin/systemctl restart app[0]",
            "!/usr/bin/sh",
            "/usr/bin/foo !bar",
            "/usr/bin/env FOO=bar",
            "/usr/bin/foo (bar)",
            '/usr/bin/foo "bar"',
            "/usr/bin/foo 'bar'",
        ],
    )
    def test_rejects_unsafe_sudo_commands(self, command: str) -> None:
        with pytest.raises(ValidationError):
            UserMold(
                name="ci",
                role=UserRole.DEPLOY,
                sudo_commands=[command],
            )

    @pytest.mark.parametrize("password", ["bad\npass", "bad\rpass", "bad\x00pass", "bad\x7fpass"])
    def test_rejects_password_with_control_chars(self, password: str) -> None:
        with pytest.raises(ValidationError, match="control characters"):
            UserMold(name="ops", password=password)

    def test_accepts_valid_deploy_commands(self) -> None:
        user = UserMold(
            name="ci",
            role=UserRole.DEPLOY,
            sudo_commands=["/usr/bin/systemctl restart app.service", "/usr/bin/podman ps"],
        )
        assert user.sudo_commands == [
            "/usr/bin/systemctl restart app.service",
            "/usr/bin/podman ps",
        ]

    def test_password_redacted_in_to_json(self) -> None:
        opts = UserMold(name="test", password="secret")
        dumped = opts.to_json()
        assert dumped["password"] == REDACTED_VALUE


class TestFeaturesMoldUsersValidation:
    def test_rejects_duplicate_user_names(self) -> None:
        with pytest.raises(ValidationError, match="Duplicate user name"):
            FeaturesMold(
                users=UsersMold(
                    users=[
                        UserMold(name="dup"),
                        UserMold(name="dup"),
                    ]
                )
            )

    def test_rejects_sanitized_sudoers_filename_collision(self) -> None:
        with pytest.raises(ValidationError, match="collides"):
            FeaturesMold(
                users=UsersMold(
                    users=[
                        UserMold(name="alice.ops"),
                        UserMold(name="alice_ops"),
                    ]
                )
            )

    def test_accepts_unique_names_and_no_collision(self) -> None:
        features = FeaturesMold(
            users=UsersMold(
                users=[
                    UserMold(name="alice.ops"),
                    UserMold(name="bob"),
                ]
            )
        )
        assert len(features.users) == 2

    def test_empty_users_list_is_valid(self) -> None:
        features = FeaturesMold(users=UsersMold())
        assert features.users.users == []


class TestUsersMoldRedaction:
    def test_users_mold_passwords_redacted_in_to_json(self) -> None:
        features = FeaturesMold(
            users=UsersMold(
                users=[
                    UserMold(name="alice", password="pw1"),
                    UserMold(name="bob", password="pw2"),
                ]
            )
        )
        dumped = features.to_json()

        # users dump: dict with users key containing list of entries
        assert "users" in dumped
        users_data = dumped["users"]
        assert isinstance(users_data, dict)
        assert "users" in users_data
        users_list = users_data["users"]
        assert isinstance(users_list, list)
        assert len(users_list) == 2

        # every password redacted
        for user_data in users_list:
            assert user_data["password"] == REDACTED_VALUE

        # raw passwords absent from JSON dump
        json_str = __import__("json").dumps(dumped)
        assert "pw1" not in json_str
        assert "pw2" not in json_str

    def test_users_mold_nested_redaction(self) -> None:
        # direct UsersMold to_json via FeaturesMold path
        features = FeaturesMold(users=UsersMold(users=[UserMold(name="charlie", password="secret123")]))
        dumped = features.to_json()

        user_data = dumped["users"]["users"][0]
        assert user_data["name"] == "charlie"
        assert user_data["password"] == REDACTED_VALUE

        json_str = __import__("json").dumps(dumped)
        assert "secret123" not in json_str
