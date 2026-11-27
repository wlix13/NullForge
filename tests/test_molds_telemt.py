import pytest
from pydantic import ValidationError

from nullforge.molds import TelemtMold


VALID_SECRET = "bf777cca8384a074a671460d51e4e31f"


class TestEnabledValidation:
    def test_install_requires_users(self) -> None:
        with pytest.raises(ValidationError, match="at least one entry in `users`"):
            TelemtMold(install=True, tls_domain="example.com")

    def test_install_tls_requires_domain(self) -> None:
        with pytest.raises(ValidationError, match="tls_domain` is required"):
            TelemtMold(install=True, users={"a": VALID_SECRET})

    def test_install_requires_a_mode(self) -> None:
        with pytest.raises(ValidationError, match="at least one of"):
            TelemtMold(
                install=True,
                tls_domain="example.com",
                users={"a": VALID_SECRET},
                mode_tls=False,
            )

    def test_secure_mode_without_domain_ok(self) -> None:
        mold = TelemtMold(
            install=True,
            users={"a": VALID_SECRET},
            mode_tls=False,
            mode_secure=True,
        )
        assert mold.is_active is True

    def test_disabled_skips_validation(self) -> None:
        # An off feature must never raise even when otherwise incomplete.
        assert TelemtMold(install=False).is_active is False


class TestUserValidation:
    def test_uppercase_secret_normalized(self) -> None:
        mold = TelemtMold(install=True, tls_domain="d", users={"a": VALID_SECRET.upper()})
        assert mold.users["a"] == VALID_SECRET

    def test_secret_wrong_length_rejected(self) -> None:
        with pytest.raises(ValidationError, match="32 hexadecimal"):
            TelemtMold(install=True, tls_domain="d", users={"a": "deadbeef"})

    def test_secret_non_hex_rejected(self) -> None:
        with pytest.raises(ValidationError, match="32 hexadecimal"):
            TelemtMold(install=True, tls_domain="d", users={"a": "z" * 32})

    def test_username_bad_chars_rejected(self) -> None:
        with pytest.raises(ValidationError, match="Invalid telemt username"):
            TelemtMold(install=True, tls_domain="d", users={"bad name": VALID_SECRET})


class TestRedaction:
    def test_users_redacted_in_json(self) -> None:
        mold = TelemtMold(install=True, tls_domain="example.com", users={"a": VALID_SECRET})
        dumped = mold.to_json()
        assert dumped["users"] == "***"
        assert VALID_SECRET not in str(dumped)
