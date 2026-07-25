from unittest.mock import patch

import pytest

from nullforge.smithy.http import fetch_github_keys, fetch_text


class TestFetchText:
    def test_rejects_non_https_url(self) -> None:
        with pytest.raises(ValueError, match="Refusing non-HTTPS URL"):
            fetch_text("http://github.com/octocat.keys")


class TestFetchGithubKeys:
    def test_none_returns_empty(self) -> None:
        assert fetch_github_keys(None) == []

    def test_returns_lines(self) -> None:
        with patch(
            "nullforge.smithy.http.fetch_text",
            return_value="ssh-ed25519 AAA a\nssh-rsa BBB b\n",
        ):
            assert fetch_github_keys("octocat") == ["ssh-ed25519 AAA a", "ssh-rsa BBB b"]

    def test_fetch_failure_warns_and_returns_empty(self) -> None:
        with patch(
            "nullforge.smithy.http.fetch_text",
            side_effect=RuntimeError("404"),
        ):
            assert fetch_github_keys("bad") == []
