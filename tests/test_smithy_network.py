from unittest.mock import MagicMock, patch

from nullforge.smithy.network import conntrack_max_for, has_ipv6, module_loaded


class _FakeData:
    pass


def _make_host(grub_contents: list[str] | None = None, ip6_raw: str = "") -> MagicMock:
    host = MagicMock()
    host.data = _FakeData()

    def get_fact(fact_class, *args, **kwargs):
        name = fact_class.__name__ if hasattr(fact_class, "__name__") else str(fact_class)
        if "FileContents" in name:
            return grub_contents
        return ip6_raw

    host.get_fact.side_effect = get_fact
    return host


def _raw_native(addr: str = "2001:db8::1/64", iface: str = "eth0") -> str:
    return f"2: {iface}    inet6 {addr} scope global"


class TestHasIpv6:
    def _call(self, grub: list[str] | None = None, ip6_raw: str = "") -> bool:
        host = _make_host(grub, ip6_raw)
        with patch("nullforge.smithy.network.host", host):
            return has_ipv6()

    def test_disabled_in_grub(self) -> None:
        grub = ['GRUB_CMDLINE_LINUX_DEFAULT="ipv6.disable=1 quiet"']
        assert self._call(grub=grub) is False

    def test_enabled_by_native_ipv6(self) -> None:
        assert self._call(ip6_raw=_raw_native()) is True

    def test_zero_ip6_interfaces(self) -> None:
        assert self._call(ip6_raw="") is False

    def test_no_grub_file(self) -> None:
        assert self._call(grub=None, ip6_raw=_raw_native()) is True

    def test_grub_without_ipv6_disable(self) -> None:
        grub = ['GRUB_CMDLINE_LINUX_DEFAULT="quiet splash"']
        assert self._call(grub=grub, ip6_raw=_raw_native()) is True

    def test_raw_facts_fetched_at_most_once_across_variants(self) -> None:
        host = _make_host(ip6_raw=_raw_native())
        with patch("nullforge.smithy.network.host", host):
            assert has_ipv6(exclude_iface="warp") is True
            assert has_ipv6() is True
            assert has_ipv6(exclude_iface="warp") is True
            assert has_ipv6() is True
            assert has_ipv6(exclude_iface="eth0") is False
        assert host.get_fact.call_count == 2

    def test_raw_facts_fetched_at_most_once_plain_first(self) -> None:
        host = _make_host(ip6_raw=_raw_native())
        with patch("nullforge.smithy.network.host", host):
            assert has_ipv6() is True
            assert has_ipv6() is True
            assert has_ipv6(exclude_iface="warp") is True
            assert has_ipv6(exclude_iface="eth0") is False
        assert host.get_fact.call_count == 2

    def test_warp_interface_ignored(self) -> None:
        raw = "3: warp    inet6 2606:4700:103::1/128 scope global"
        assert self._call(ip6_raw=raw) is False

    def test_only_tunnel_ifaces_yield_false_even_with_other_tunnels(self) -> None:
        raw = (
            "3: warp    inet6 2606:4700:103::1/128 scope global\n"
            "5: wg0     inet6 fe80::1/64 scope global\n"  # link-local shouldn't count anyway
            "6: docker0 inet6 2001:db8:dead::1/64 scope global"
        )
        assert self._call(ip6_raw=raw) is False


class TestConntrackMaxFor:
    def test_floor_for_tiny_ram(self) -> None:
        # 128 MB -> ~8947 entries -> clamped up to the 16384 floor
        assert conntrack_max_for(128) == 16384

    def test_ceiling_for_huge_ram(self) -> None:
        # 256 GB -> way above the ceiling -> clamped to 512Ki
        assert conntrack_max_for(256 * 1024) == 512 * 1024

    def test_scales_with_ram(self) -> None:
        # 8 GB -> 8192 * 1024 * 1024 * 0.02 / 300 ~ 572662 -> clamped to ceiling
        assert conntrack_max_for(8192) == 512 * 1024
        # 2 GB -> 2048 * 1024 * 1024 * 0.02 / 300 ~ 143165 -> within bounds
        assert conntrack_max_for(2048) == int(2048 * 1024 * 1024 * 0.02 / 300)


def _make_modules_host(modules: object) -> MagicMock:
    host = MagicMock()
    host.data = _FakeData()
    host.get_fact.return_value = modules
    return host


class TestModuleLoaded:
    def _call(self, modules: object, module: str) -> bool:
        host = _make_modules_host(modules)
        with patch("nullforge.smithy.network.host", host):
            return module_loaded(module)

    def test_true_when_present(self) -> None:
        assert self._call({"nf_conntrack": {"size": "180224"}}, "nf_conntrack") is True

    def test_false_when_absent(self) -> None:
        assert self._call({"overlay": {"size": "0"}}, "nf_conntrack") is False

    def test_false_when_fact_empty(self) -> None:
        assert self._call(None, "nf_conntrack") is False

    def test_caching_shared_across_modules(self) -> None:
        host = _make_modules_host({"nf_conntrack": {}, "overlay": {}})
        with patch("nullforge.smithy.network.host", host):
            assert module_loaded("nf_conntrack") is True
            assert module_loaded("overlay") is True
            assert module_loaded("br_netfilter") is False
        # single fact gather serves every subsequent module check
        assert host.get_fact.call_count == 1
