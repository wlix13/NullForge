from typing import Any, Literal

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


class TestSynfix:
    def test_defaults_to_disabled(self) -> None:
        assert TelemtMold().synfix is None

    @pytest.mark.parametrize("variant", ["v2", "v3", "v4"])
    def test_accepts_all_variants(self, variant: Literal["v2", "v3", "v4"]) -> None:
        assert TelemtMold(synfix=variant).synfix == variant

    def test_rejects_unknown_variant(self) -> None:
        with pytest.raises(ValidationError):
            TelemtMold.model_validate({"synfix": "v5"})


class TestWebMode:
    def _base(self, **kwargs: Any) -> TelemtMold:
        kwargs.setdefault("web_host", "pulsar.example.com")
        return TelemtMold(
            install=True,
            tls_domain="example.com",
            users={"a": VALID_SECRET},
            port=8443,
            mode_web=True,
            **kwargs,
        )

    def test_web_disabled_by_default(self) -> None:
        assert TelemtMold().mode_web is False

    def test_web_accepted_off_port_443(self) -> None:
        mold = self._base()
        assert mold.web_host == "pulsar.example.com"
        assert mold.web_carrier == "https"

    def test_web_requires_host(self) -> None:
        with pytest.raises(ValidationError, match="web_host"):
            TelemtMold(install=True, tls_domain="example.com", users={"a": VALID_SECRET}, mode_web=True)

    def test_web_on_port_443_rejected(self) -> None:
        with pytest.raises(ValidationError, match="port 443"):
            TelemtMold(
                install=True,
                tls_domain="example.com",
                users={"a": VALID_SECRET},
                port=443,
                mode_web=True,
                web_host="pulsar.example.com",
            )

    def test_web_user_must_exist_in_users(self) -> None:
        with pytest.raises(ValidationError, match="web_user"):
            self._base(web_user="ghost")

    def test_web_user_accepted_when_listed(self) -> None:
        assert self._base(web_user="a").mode_web is True

    def test_base_path_validation(self) -> None:
        with pytest.raises(ValidationError, match="web_base_path"):
            self._base(web_base_path="/bad path/")
        assert self._base(web_base_path="telegram/web").web_base_path == "telegram/web"

    def test_host_normalized(self) -> None:
        assert self._base(web_host=" Pulsar.Example.COM ").web_host == "pulsar.example.com"

    def test_public_addr_must_be_literal_socket_address(self) -> None:
        with pytest.raises(ValidationError, match="ip:port"):
            self._base(web_public_addr="pulsar.example.com:443")
        assert self._base(web_public_addr="203.0.113.10:443").web_public_addr == "203.0.113.10:443"
