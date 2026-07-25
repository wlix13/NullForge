from unittest.mock import patch

from nullforge.models.system import SwapAlgo, SwapType
from nullforge.molds.system import SwapMold, SystemMold
from nullforge.smithy.swap import configure_swap


def _make_system(enabled: bool = True, swap_type: SwapType = SwapType.ZRAM, size: str = "2G") -> SystemMold:
    return SystemMold(swap=SwapMold(enabled=enabled, type=swap_type, size=size))


class TestConfigureSwap:
    def test_disabled_calls_disable(self) -> None:
        system = _make_system(enabled=False)
        with patch("nullforge.smithy.swap._disable_swap") as mock_disable:
            with patch("nullforge.smithy.swap._set_swappiness"):
                configure_swap(system)
        mock_disable.assert_called_once()

    def test_disabled_skips_configure(self) -> None:
        system = _make_system(enabled=False)
        with patch("nullforge.smithy.swap._disable_swap"):
            with patch("nullforge.smithy.swap._configure_zram") as mock_zram:
                with patch("nullforge.smithy.swap._configure_basic_swap") as mock_basic:
                    configure_swap(system)
        mock_zram.assert_not_called()
        mock_basic.assert_not_called()

    def test_zram_calls_configure_zram(self) -> None:
        system = _make_system(enabled=True, swap_type=SwapType.ZRAM, size="4G")
        with patch("nullforge.smithy.swap._disable_basic_swap"):
            with patch("nullforge.smithy.swap._configure_zram") as mock_zram:
                with patch("nullforge.smithy.swap._set_swappiness"):
                    with patch("nullforge.smithy.swap._disable_zram"):
                        configure_swap(system)
        mock_zram.assert_called_once_with("4G", SwapAlgo.ZSTD)

    def test_file_swap_calls_configure_basic(self) -> None:
        system = _make_system(enabled=True, swap_type=SwapType.BASIC, size="1G")
        with patch("nullforge.smithy.swap._disable_zram"):
            with patch("nullforge.smithy.swap._configure_basic_swap") as mock_basic:
                with patch("nullforge.smithy.swap._set_swappiness"):
                    with patch("nullforge.smithy.swap._disable_basic_swap"):
                        configure_swap(system)
        mock_basic.assert_called_once_with("1G")

    def test_swappiness_always_set_when_enabled(self) -> None:
        system = _make_system(enabled=True, swap_type=SwapType.ZRAM)
        with patch("nullforge.smithy.swap._disable_basic_swap"):
            with patch("nullforge.smithy.swap._configure_zram"):
                with patch("nullforge.smithy.swap._set_swappiness") as mock_sw:
                    with patch("nullforge.smithy.swap._disable_zram"):
                        configure_swap(system)
        mock_sw.assert_called_once_with(system.swap.swappiness)
