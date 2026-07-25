from unittest.mock import patch

import pytest

from nullforge.models.netsec import (
    CLASSICAL_KEX_ALGORITHMS,
    PQ_KEX_ALGORITHMS,
    WEAK_KEX_PATTERNS,
    WEAK_MAC_PATTERNS,
    SshHostKeyType,
)
from nullforge.molds.netsec import FirewallRule, SshMold
from nullforge.runes import netsec as netsec_rune
from nullforge.runes.netsec import (
    _build_firewalld_commands,
    _build_sshd_dropin,
    _build_ufw_command,
    _resolve_conntrack_sysctls,
    _supported_kex_algorithms,
)
from nullforge.smithy.network import conntrack_max_for


class TestBuildUfwCommand:
    def _rule(self, **kwargs) -> FirewallRule:
        return FirewallRule(**kwargs)

    def test_basic_allow(self) -> None:
        cmd = _build_ufw_command(self._rule(port=22, action="allow"))
        assert "ufw allow" in cmd
        assert "port 22" in cmd

    def test_deny_with_proto(self) -> None:
        cmd = _build_ufw_command(self._rule(port=80, action="deny", proto="tcp"))
        assert "deny" in cmd
        assert "proto tcp" in cmd

    def test_from_ip(self) -> None:
        cmd = _build_ufw_command(self._rule(from_ip="10.0.0.0/8", action="allow"))
        assert "from 10.0.0.0/8" in cmd

    def test_any_proto_omitted(self) -> None:
        cmd = _build_ufw_command(self._rule(port=22, proto="any"))
        assert "proto" not in cmd

    def test_comment_included(self) -> None:
        cmd = _build_ufw_command(self._rule(port=22, comment="SSH"))
        assert '"SSH"' in cmd

    def test_interface_included(self) -> None:
        cmd = _build_ufw_command(self._rule(port=443, interface="eth0"))
        assert "on eth0" in cmd


class TestBuildFirewalldCommands:
    def _rule(self, **kwargs) -> FirewallRule:
        return FirewallRule(**kwargs)

    def test_simple_allow_port_tcp(self) -> None:
        cmds = _build_firewalld_commands(self._rule(port=80, proto="tcp", action="allow"))
        assert len(cmds) == 1
        assert "--add-port=80/tcp" in cmds[0]

    def test_simple_allow_port_any_generates_two(self) -> None:
        cmds = _build_firewalld_commands(self._rule(port=443, proto="any", action="allow"))
        assert len(cmds) == 2
        assert any("tcp" in c for c in cmds)
        assert any("udp" in c for c in cmds)

    def test_rich_rule_with_source(self) -> None:
        cmds = _build_firewalld_commands(self._rule(port=22, proto="tcp", from_ip="10.0.0.0/8", action="allow"))
        assert len(cmds) == 1
        assert "add-rich-rule" in cmds[0]
        assert "source" in cmds[0]

    def test_deny_action(self) -> None:
        cmds = _build_firewalld_commands(self._rule(port=22, action="deny", from_ip="1.2.3.4"))
        assert "drop" in cmds[0]

    def test_out_direction_raises(self) -> None:
        with pytest.raises(ValueError, match="direction='out'"):
            _build_firewalld_commands(self._rule(port=22, direction="out"))

    def test_limit_action_raises(self) -> None:
        with pytest.raises(ValueError, match="action='limit'"):
            _build_firewalld_commands(self._rule(port=22, action="limit"))

    def test_no_port_no_proto_in_rich_rule(self) -> None:
        cmds = _build_firewalld_commands(self._rule(from_ip="10.0.0.0/8", action="deny"))
        assert "port" not in cmds[0]


class TestResolveConntrackSysctls:
    MAX_KEY = "net.netfilter.nf_conntrack_max"
    TOTAL_MEMORY = 2048

    def test_none_passes_through(self) -> None:
        assert _resolve_conntrack_sysctls(None) is None

    def test_empty_passes_through(self) -> None:
        assert _resolve_conntrack_sysctls({}) == {}

    def test_skipped_when_module_not_loaded(self) -> None:
        with patch("nullforge.runes.netsec.module_loaded", return_value=False):
            assert _resolve_conntrack_sysctls({"net.netfilter.nf_conntrack_udp_timeout": 30}) is None

    def test_injects_ram_derived_sizing(self) -> None:
        with (
            patch("nullforge.runes.netsec.module_loaded", return_value=True),
            patch("nullforge.runes.netsec.get_total_memory", return_value=self.TOTAL_MEMORY),
        ):
            result = _resolve_conntrack_sysctls({"net.netfilter.nf_conntrack_udp_timeout": 30})

        ct_max_target = conntrack_max_for(self.TOTAL_MEMORY)
        ct_buckets = max(4096, (ct_max_target + 3) // 4)
        assert result is not None
        assert result[self.MAX_KEY] == ct_buckets * 4
        assert ct_max_target <= result[self.MAX_KEY] <= ct_max_target + 3
        # configured timeouts are preserved alongside the injected sizing
        assert result["net.netfilter.nf_conntrack_udp_timeout"] == 30

    def test_explicit_max_overrides_runtime_value(self) -> None:
        with (
            patch("nullforge.runes.netsec.module_loaded", return_value=True),
            patch("nullforge.runes.netsec.get_total_memory", return_value=self.TOTAL_MEMORY),
        ):
            result = _resolve_conntrack_sysctls({self.MAX_KEY: 99})

        assert result is not None
        assert result[self.MAX_KEY] == 99


class TestBuildSshdDropin:
    ALL_SUPPORTED = frozenset(PQ_KEX_ALGORITHMS + CLASSICAL_KEX_ALGORITHMS)

    def test_everything_off_renders_nothing(self) -> None:
        mold = SshMold(pq_kex_priority=False, strip_weak_algorithms=False)
        assert _build_sshd_dropin(mold, self.ALL_SUPPORTED) == ""

    def test_pq_only_filters_unsupported_algorithms(self) -> None:
        supported = frozenset({"sntrup761x25519-sha512@openssh.com", "curve25519-sha256"})
        content = _build_sshd_dropin(SshMold(strip_weak_algorithms=False), supported)
        assert "KexAlgorithms ^sntrup761x25519-sha512@openssh.com" in content
        assert "mlkem768" not in content

    def test_pq_only_without_support_renders_nothing(self) -> None:
        assert _build_sshd_dropin(SshMold(strip_weak_algorithms=False), frozenset()) == ""

    def test_strip_allowlist_filters_unsupported(self) -> None:
        supported = frozenset({"mlkem768x25519-sha256", "curve25519-sha256"})
        content = _build_sshd_dropin(SshMold(), supported)
        assert "KexAlgorithms mlkem768x25519-sha256,curve25519-sha256\n" in content

    def test_strip_without_pq_support_falls_back_to_removal_patterns(self) -> None:
        content = _build_sshd_dropin(SshMold(), frozenset())
        assert f"KexAlgorithms -{WEAK_KEX_PATTERNS}" in content

    def test_strip_with_pq_disabled_uses_removal_patterns(self) -> None:
        content = _build_sshd_dropin(SshMold(pq_kex_priority=False), self.ALL_SUPPORTED)
        assert f"KexAlgorithms -{WEAK_KEX_PATTERNS}" in content

    def test_strip_adds_mac_and_ca_directives(self) -> None:
        content = _build_sshd_dropin(SshMold(), self.ALL_SUPPORTED)
        assert f"MACs -{WEAK_MAC_PATTERNS}" in content
        assert "CASignatureAlgorithms -ssh-rsa" in content

    def test_no_strip_omits_mac_and_ca_directives(self) -> None:
        content = _build_sshd_dropin(SshMold(strip_weak_algorithms=False), self.ALL_SUPPORTED)
        assert "MACs" not in content
        assert "CASignatureAlgorithms" not in content

    def test_host_keys_render_hostkey_lines_and_explicit_algorithms(self) -> None:
        mold = SshMold(
            host_keys=[SshHostKeyType.ED25519, SshHostKeyType.RSA],
            pq_kex_priority=False,
            strip_weak_algorithms=False,
        )
        content = _build_sshd_dropin(mold, frozenset())
        assert content.splitlines()[1:] == [
            "HostKey /etc/ssh/ssh_host_ed25519_key",
            "HostKey /etc/ssh/ssh_host_rsa_key",
            "HostKeyAlgorithms ssh-ed25519,rsa-sha2-512,rsa-sha2-256",
        ]
        assert "ecdsa" not in content


class TestFilterDhModuli:
    def test_skips_when_no_weak_moduli(self) -> None:
        with patch.object(netsec_rune.host, "get_fact", return_value=""):
            assert netsec_rune._filter_dh_moduli() is None

    def test_filters_when_weak_moduli_present(self) -> None:
        with patch.object(netsec_rune.host, "get_fact", return_value="20250101 2 6 100 2047 2 c0ffee"):
            assert netsec_rune._filter_dh_moduli() is not None


class TestSupportedKexAlgorithms:
    def test_parses_and_strips_command_output(self) -> None:
        with patch.object(netsec_rune.host, "get_fact", return_value="curve25519-sha256\n mlkem768x25519-sha256 \n\n"):
            assert _supported_kex_algorithms() == frozenset({"curve25519-sha256", "mlkem768x25519-sha256"})

    def test_empty_output_yields_empty_set(self) -> None:
        with patch.object(netsec_rune.host, "get_fact", return_value=""):
            assert _supported_kex_algorithms() == frozenset()
