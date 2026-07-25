import pytest
from pydantic import ValidationError

from nullforge.molds.user import UserMold


class TestFetchKeyFromGithub:
    @pytest.mark.parametrize(
        "username",
        ["octocat", "mojombo", "a"],
    )
    def test_accepts_valid_username(self, username: str) -> None:
        assert UserMold(fetch_key_from_github=username).fetch_key_from_github == username

    @pytest.mark.parametrize(
        "username",
        ["", "-octocat", "user_name", "user.name", "with space", "a" * 40],
    )
    def test_rejects_invalid_username(self, username: str) -> None:
        with pytest.raises(ValidationError):
            UserMold(fetch_key_from_github=username)
