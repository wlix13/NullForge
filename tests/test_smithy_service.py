from unittest.mock import MagicMock, patch

import pytest

from nullforge.smithy.admin import is_root
from nullforge.smithy.service import ensure_service_user


class _FakeData:
    pass


def _make_service_context(groups: list[str], users: list[str]) -> tuple[MagicMock, MagicMock]:
    """Create a patched host and server mock for ensure_service_user tests."""
    host = MagicMock()
    host.data = _FakeData()
    host.get_fact.side_effect = lambda fact, **kw: groups if "Groups" in str(fact) else users
    server = MagicMock()
    return host, server


class TestIsRoot:
    def test_caching(self) -> None:
        host = MagicMock()
        host.data = _FakeData()
        host.get_fact.return_value = "root"
        with patch("nullforge.smithy.admin.host", host):
            is_root()
            is_root()
        assert host.get_fact.call_count == 1


@pytest.mark.parametrize(
    "groups,users,expect_group_create,expect_user_create",
    [
        ([], [], True, True),
        ([], ["myuser"], True, False),
        (["mygroup"], [], False, True),
        (["mygroup"], ["myuser"], False, False),
    ],
)
def test_ensure_service_user(
    groups: list[str],
    users: list[str],
    expect_group_create: bool,
    expect_user_create: bool,
) -> None:
    host, server = _make_service_context(groups, users)
    with patch("nullforge.smithy.service.host", host):
        with patch("nullforge.smithy.service.server", server):
            with patch("nullforge.smithy.service.files", MagicMock()):
                ensure_service_user("myuser", "mygroup", "/etc/myservice")
    assert server.group.called is expect_group_create
    assert server.user.called is expect_user_create
    if expect_group_create:
        group_call_args = server.group.call_args
        assert group_call_args.kwargs.get("system") is True
    if expect_user_create:
        user_call_args = server.user.call_args
        assert user_call_args.kwargs.get("system") is True
        assert user_call_args.kwargs.get("create_home") is False
