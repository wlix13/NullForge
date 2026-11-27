from ipaddress import IPv4Address, IPv6Address

import pytest

from nullforge.molds import DnsMold


class TestDnsMoldListenAddress:
    @pytest.mark.parametrize(
        "addr",
        [
            "0.0.0.0",
            "::",
            "127.0.0.1",
            "::1",
        ],
    )
    def test_not_need_custom_interface(self, addr: str) -> None:
        mold = DnsMold(listen_address=addr)
        assert isinstance(mold.listen_address, IPv4Address | IPv6Address)
        assert mold.needs_custom_interface is False

    @pytest.mark.parametrize(
        "addr",
        [
            "169.254.0.53",
            "10.0.0.53",
            "192.0.2.1",
            "2001:db8::1",
            "fd00::53",
            "fe80::53",
        ],
    )
    def test_need_custom_interface(self, addr: str) -> None:
        mold = DnsMold(listen_address=addr)
        assert isinstance(mold.listen_address, IPv4Address | IPv6Address)
        assert mold.needs_custom_interface is True

    @pytest.mark.parametrize(
        "addr",
        [
            "8.8.8.8",
            "1.1.1.1",
            "2001:4860:4860::8888",
            "2606:4700:4700::1111",
        ],
    )
    def test_public_addresses_rejected(self, addr: str) -> None:
        with pytest.raises(ValueError):
            DnsMold(listen_address=addr)
