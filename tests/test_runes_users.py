from unittest.mock import MagicMock, patch

from pyinfra.facts.files import FileContents

from nullforge.molds.user import UserMold
from nullforge.runes.users import _dedup_keys, _install_ssh_keys


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
        opts = UserMold(copy_root_keys=False, fetch_key_from_github="octocat")

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
        opts = UserMold(copy_root_keys=True, fetch_key_from_github="bad")

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
