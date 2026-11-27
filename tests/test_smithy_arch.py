from unittest.mock import MagicMock, patch

from nullforge.smithy.arch import arch_id, deb_arch


class _FakeData:
    pass


def _make_arch_host(arch_string: str) -> MagicMock:
    host = MagicMock()
    host.get_fact.return_value = arch_string
    host.data = _FakeData()
    return host


class TestArchId:
    def _call(self, arch_string: str) -> str:
        host = _make_arch_host(arch_string)
        with patch("nullforge.smithy.arch.host", host):
            return arch_id()

    def test_amd64_normalized(self) -> None:
        assert self._call("amd64") == "x86_64"

    def test_aarch64_normalized(self) -> None:
        assert self._call("aarch64") == "arm64"

    def test_unknown_passthrough(self) -> None:
        assert self._call("riscv64") == "riscv64"

    def test_caching(self) -> None:
        host = _make_arch_host("x86_64")
        with patch("nullforge.smithy.arch.host", host):
            arch_id()
            arch_id()
        assert host.get_fact.call_count == 1


class TestDebArch:
    def _call(self, arch_string: str) -> str:
        host = _make_arch_host(arch_string)
        with patch("nullforge.smithy.arch.host", host):
            return deb_arch()

    def test_x86_64_returns_amd64(self) -> None:
        assert self._call("x86_64") == "amd64"

    def test_arm64_returns_arm64(self) -> None:
        assert self._call("arm64") == "arm64"

    def test_unknown_defaults_to_amd64(self) -> None:
        assert self._call("riscv64") == "amd64"
