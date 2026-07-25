from nullforge.models.dns import DnsServerDoH, DnsServerDoT
from nullforge.runes.dns import _format_blocky_upstreams


class TestFormatBlockyUpstreams:
    def test_doh_server(self) -> None:
        srv = DnsServerDoH(url="https://1.1.1.1/dns-query")
        result = _format_blocky_upstreams([srv])
        assert result == ["https://1.1.1.1/dns-query"]

    def test_dot_server_ipv4(self) -> None:
        srv = DnsServerDoT(host="1.1.1.1", sni="cloudflare-dns.com")
        result = _format_blocky_upstreams([srv])
        assert result == ["tcp-tls:1.1.1.1:853"]

    def test_dot_server_ipv6_brackets(self) -> None:
        srv = DnsServerDoT(host="2606:4700:4700::1111", port=853)
        result = _format_blocky_upstreams([srv])
        assert result == ["tcp-tls:[2606:4700:4700::1111]:853"]
