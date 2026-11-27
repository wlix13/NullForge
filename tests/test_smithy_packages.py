from unittest.mock import MagicMock

from nullforge.smithy.packages import PackageManager


def _make_pm(distro_name: str, major: int = 0) -> PackageManager:
    host = MagicMock()
    host.get_fact.return_value = {"name": distro_name, "major": major}
    host.data = MagicMock()
    return PackageManager(host)


class TestDebian:
    def test_passthrough_known_package(self) -> None:
        pm = _make_pm("ubuntu")
        assert pm.map_package("curl") == "curl"

    def test_ubuntu_override(self) -> None:
        pm = _make_pm("ubuntu")
        assert pm.map_package("ifupdown2") == "ifupdown"

    def test_debian_no_override(self) -> None:
        pm = _make_pm("debian")
        assert pm.map_package("ifupdown2") == "ifupdown2"


class TestRhel:
    def test_known_override(self) -> None:
        pm = _make_pm("rhel")
        assert pm.map_package("dnsutils") == "bind-utils"

    def test_none_skip(self) -> None:
        pm = _make_pm("fedora")
        assert pm.map_package("apt-transport-https") is None

    def test_passthrough_unknown(self) -> None:
        pm = _make_pm("centos")
        assert pm.map_package("some-unknown-pkg") == "some-unknown-pkg"

    def test_map_packages_skips_none(self) -> None:
        pm = _make_pm("rhel")
        result = pm.map_packages(["dnsutils", "apt-transport-https"])
        assert "bind-utils" in result
        assert None not in result
