import pytest
from pydantic import ValidationError

from nullforge.models.netsec import SshHostKeyType
from nullforge.molds.netsec import FirewallRule, SshMold


class TestFirewallRuleIsIpv6:
    def _rule(self, from_ip: str | None = None, to_ip: str | None = None) -> FirewallRule:
        return FirewallRule(from_ip=from_ip, to_ip=to_ip)

    def test_no_ips_is_not_ipv6(self) -> None:
        assert self._rule().is_ipv6 is False

    def test_ipv4_from_is_not_ipv6(self) -> None:
        assert self._rule(from_ip="192.168.1.1").is_ipv6 is False

    def test_ipv6_from_is_ipv6(self) -> None:
        assert self._rule(from_ip="2001:db8::1").is_ipv6 is True

    def test_ipv6_cidr_is_ipv6(self) -> None:
        assert self._rule(from_ip="2001:db8::/32").is_ipv6 is True

    def test_mixed_ipv4_ipv6_is_not_ipv6(self) -> None:
        assert self._rule(from_ip="192.168.1.1", to_ip="2001:db8::1").is_ipv6 is False

    def test_both_ipv6_is_ipv6(self) -> None:
        assert self._rule(from_ip="2001:db8::1", to_ip="2001:db8::2").is_ipv6 is True

    def test_any_keyword_is_not_ipv6(self) -> None:
        assert self._rule(from_ip="any").is_ipv6 is False

    def test_invalid_ip_returns_false(self) -> None:
        assert self._rule(from_ip="not-an-ip").is_ipv6 is False


class TestSshMold:
    def test_empty_host_keys_rejected(self) -> None:
        with pytest.raises(ValidationError, match="at least one host key"):
            SshMold(host_keys=[])

    def test_host_keys_coerce_and_dedupe(self) -> None:
        mold = SshMold.model_validate({"host_keys": ["ed25519", "rsa", "ed25519"]})
        assert mold.host_keys == [SshHostKeyType.ED25519, SshHostKeyType.RSA]
