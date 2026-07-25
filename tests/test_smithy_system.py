from unittest.mock import MagicMock, patch

from nullforge.smithy.system import detect_best_locale, get_supported_locales, get_total_memory


class _FakeData:
    pass


def _make_memory_host(memory: object) -> MagicMock:
    host = MagicMock()
    host.data = _FakeData()
    host.get_fact.return_value = memory
    return host


class TestGetTotalMemoryMb:
    def _call(self, memory: object, default: int = 1024) -> int:
        host = _make_memory_host(memory)
        with patch("nullforge.smithy.system.host", host):
            return get_total_memory(default=default)

    def test_falls_back_to_default_when_none(self) -> None:
        assert self._call(None, default=512) == 512

    def test_caching(self) -> None:
        host = _make_memory_host(4096)
        with patch("nullforge.smithy.system.host", host):
            assert get_total_memory() == 4096
            assert get_total_memory() == 4096
        assert host.get_fact.call_count == 1


def _make_locale_host(locale_gen_lines: list[str] | None) -> MagicMock:
    host = MagicMock()
    host.get_fact.return_value = locale_gen_lines
    host.data = _FakeData()
    return host


class TestGetSupportedLocales:
    def _call(self, lines: list[str] | None) -> list[str]:
        host = _make_locale_host(lines)
        with patch("nullforge.smithy.system.host", host):
            return get_supported_locales()

    def test_none_returns_empty(self) -> None:
        assert self._call(None) == []

    def test_parses_enabled_locale(self) -> None:
        result = self._call(["en_US.UTF-8 UTF-8"])
        assert "en_US.UTF-8 UTF-8" in result

    def test_strips_comment_prefix(self) -> None:
        result = self._call(["# en_GB.UTF-8 UTF-8"])
        assert "en_GB.UTF-8 UTF-8" in result

    def test_skips_blank_lines(self) -> None:
        result = self._call(["", "en_US.UTF-8 UTF-8", ""])
        assert len(result) == 1

    def test_caching(self) -> None:
        host = _make_locale_host(["en_US.UTF-8 UTF-8"])
        with patch("nullforge.smithy.system.host", host):
            get_supported_locales()
            get_supported_locales()
        assert host.get_fact.call_count == 1


class TestDetectBestLocale:
    EN_US = "en_US.UTF-8 UTF-8"
    EN_GB = "en_GB.UTF-8 UTF-8"
    FR_FR = "fr_FR.UTF-8 UTF-8"

    def _call(self, supported: list[str], preferred: str | None = None) -> str | None:
        host = _make_locale_host(supported)
        with patch("nullforge.smithy.system.host", host):
            return detect_best_locale(preferred=preferred)

    def test_returns_none_when_empty(self) -> None:
        assert self._call([]) is None

    def test_exact_preferred_match(self) -> None:
        result = self._call([self.EN_US, self.EN_GB], preferred=self.EN_GB)
        assert result == self.EN_GB

    def test_prefix_preferred_match(self) -> None:
        result = self._call([self.EN_US], preferred="en_US")
        assert result == self.EN_US

    def test_falls_back_to_hardcoded_default(self) -> None:
        result = self._call([self.EN_US, self.FR_FR])
        assert result == self.EN_US

    def test_falls_back_to_utf8(self) -> None:
        result = self._call([self.FR_FR])
        assert result == self.FR_FR

    def test_returns_first_when_no_utf8(self) -> None:
        result = self._call(["C ISO-8859-1"])
        assert result == "C ISO-8859-1"
