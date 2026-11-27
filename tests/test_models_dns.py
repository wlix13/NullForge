import pytest

from nullforge.models.dns import DnsProtocol, DnsProvider, DnsProviders, DnsServerDoH, DnsServerDoT


class TestGetUpstreams:
    def test_cloudflare_doh_ipv4(self) -> None:
        servers = DnsProviders.get_upstreams(DnsProvider.CLOUDFLARE, DnsProtocol.DOH, ipv6=False)
        assert len(servers) == 2
        assert all(isinstance(s, DnsServerDoH) for s in servers)

    def test_cloudflare_dot(self) -> None:
        servers = DnsProviders.get_upstreams(DnsProvider.CLOUDFLARE, DnsProtocol.DOT, ipv6=False)
        assert len(servers) == 2
        assert all(isinstance(s, DnsServerDoT) for s in servers)
        dot_servers = [s for s in servers if isinstance(s, DnsServerDoT)]
        assert all(s.sni == "cloudflare-dns.com" for s in dot_servers)

    def test_quad9_doh_no_ecs(self) -> None:
        servers = DnsProviders.get_upstreams(DnsProvider.QUAD9, DnsProtocol.DOH, ipv6=False, ecs=False)
        doh = [s for s in servers if isinstance(s, DnsServerDoH)]
        assert len(doh) == 2
        assert all("9.9.9.10" in s.url or "149.112.112.10" in s.url for s in doh)

    def test_quad9_doh_with_ecs(self) -> None:
        servers = DnsProviders.get_upstreams(DnsProvider.QUAD9, DnsProtocol.DOH, ipv6=False, ecs=True)
        doh = [s for s in servers if isinstance(s, DnsServerDoH)]
        assert len(doh) == 2
        assert all("9.9.9.12" in s.url or "149.112.112.12" in s.url for s in doh)

    def test_ecs_raises_for_non_quad9(self) -> None:
        with pytest.raises(ValueError, match="ECS is supported only"):
            DnsProviders.get_upstreams(DnsProvider.CLOUDFLARE, DnsProtocol.DOH, ipv6=False, ecs=True)

    def test_unsupported_protocol_raises(self) -> None:
        with pytest.raises(ValueError):
            DnsProviders.get_upstreams(DnsProvider.CLOUDFLARE, DnsProtocol.DOU, ipv6=False)

    def test_ipv6_doubles_server_count(self) -> None:
        v4 = DnsProviders.get_upstreams(DnsProvider.CLOUDFLARE, DnsProtocol.DOH, ipv6=False)
        v6 = DnsProviders.get_upstreams(DnsProvider.CLOUDFLARE, DnsProtocol.DOH, ipv6=True)
        assert len(v6) == len(v4) * 2
